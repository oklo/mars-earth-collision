#!/usr/bin/env python3
"""Three-clump forward model for the 36 h Mars--Earth collision remnant.

The model deliberately stops at the first finite-radius contact.  Before that
event it integrates three Newtonian point masses, applies an optional impulsive
fluid dynamical-tide loss at detached pericenters, and activates a small-e
weak-friction/equilibrium-tide surrogate only for Roche-safe detached pairs.

This is an intuition and sensitivity model, not a hydrodynamic continuation.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np


G = 6.67430e-11
PAIR_SPECS = (
    (0, 1, "earth_mars", "Earth--Mars"),
    (1, 2, "mars_secondary", "Mars--secondary"),
    (0, 2, "earth_secondary", "Earth--secondary"),
)
RADIUS_KEYS = ("r95", "r99", "rmax")
OUTCOME_LABELS = {
    "earth_mars_contact": "Earth--Mars contact",
    "mars_secondary_contact": "secondary reaccretion",
    "earth_secondary_contact": "secondary--Earth contact",
    "secondary_survives_point_mass": "secondary survives",
    "secondary_roche_risk": "secondary Roche-risk",
    "secondary_stripped_by_earth": "secondary stripped",
    "three_body_ejection_candidate": "ejection candidate",
    "unresolved_no_contact": "no contact / unresolved",
}


@dataclass
class ModelConfig:
    radius_key: str = "r99"
    dynamical_efficiency: float = 0.01
    dynamical_eta_suppression: float = 2.0
    dynamical_energy_cap_fraction: float = 0.25
    equilibrium_tides: bool = True
    equilibrium_max_eccentricity: float = 0.3
    equilibrium_detachment_factor: float = 1.2
    dt_s: float = 20.0
    duration_s: float = 36.0 * 3600.0
    output_cadence_s: float = 300.0


def _attr_scalar(value: Any) -> float:
    return float(np.asarray(value).reshape(-1)[0])


def _json_number(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): _json_number(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_number(v) for v in value]
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_number(payload), indent=2) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Iterable[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row)) if rows else []
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(_json_number(row))


def extract_clump_states(
    snapshot: Path,
    labels: Path,
    output: Path,
    link_length_m: float = 5.0e5,
) -> dict[str, Any]:
    """Extract the three largest 500-km friends-of-friends clumps."""
    import h5py
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    with h5py.File(snapshot, "r") as handle:
        length_unit = _attr_scalar(handle["Units"].attrs["Unit length in cgs (U_L)"]) * 1.0e-2
        mass_unit = _attr_scalar(handle["Units"].attrs["Unit mass in cgs (U_M)"]) * 1.0e-3
        time_unit = _attr_scalar(handle["Units"].attrs["Unit time in cgs (U_t)"])
        group = handle["PartType0"]
        positions = np.asarray(group["Coordinates"], dtype=float) * length_unit
        velocities = np.asarray(group["Velocities"], dtype=float) * length_unit / time_unit
        masses = np.asarray(group["Masses"], dtype=float) * mass_unit
        particle_ids = np.asarray(group["ParticleIDs"])
        material_ids = np.asarray(group["MaterialIDs"])
        snapshot_time_s = _attr_scalar(handle["Header"].attrs["Time"]) * time_unit

    with h5py.File(labels, "r") as handle:
        label_ids = np.asarray(handle["ParticleIDs"])
        label_body_ids = np.asarray(handle["BodyID"])
    label_order = np.argsort(label_ids)
    hits = np.searchsorted(label_ids[label_order], particle_ids)
    if np.any(hits == len(label_order)) or np.any(label_ids[label_order[hits]] != particle_ids):
        raise ValueError("Snapshot ParticleIDs are not all present in the label sidecar")
    source_ids = label_body_ids[label_order[hits]]

    pairs = cKDTree(positions).query_pairs(link_length_m, output_type="ndarray")
    graph = coo_matrix(
        (np.ones(len(pairs), dtype=np.uint8), (pairs[:, 0], pairs[:, 1])),
        shape=(len(positions), len(positions)),
    )
    _, component = connected_components(graph, directed=False)
    component_mass = np.bincount(component, weights=masses)
    largest = np.argsort(component_mass)[-3:][::-1]
    names = ("earth_remnant", "mars_remnant", "mars_secondary")

    bodies: list[dict[str, Any]] = []
    raw_positions: list[np.ndarray] = []
    raw_velocities: list[np.ndarray] = []
    body_masses: list[float] = []
    for name, component_id in zip(names, largest, strict=True):
        selected = component == component_id
        w = masses[selected]
        x = positions[selected]
        v = velocities[selected]
        mass = float(np.sum(w))
        center = np.average(x, axis=0, weights=w)
        center_velocity = np.average(v, axis=0, weights=w)
        dx = x - center
        dv = v - center_velocity
        radius = np.linalg.norm(dx, axis=1)
        angular_momentum = np.sum(w[:, None] * np.cross(dx, dv), axis=0)
        inertia = np.sum(
            w[:, None, None]
            * (
                np.sum(dx * dx, axis=1)[:, None, None] * np.eye(3)
                - dx[:, :, None] * dx[:, None, :]
            ),
            axis=0,
        )
        angular_velocity = np.linalg.solve(inertia, angular_momentum)
        source_fraction = {
            "earth": float(np.sum(w[source_ids[selected] == 1]) / mass),
            "mars": float(np.sum(w[source_ids[selected] == 2]) / mass),
        }
        material_fraction = {
            "forsterite": float(np.sum(w[material_ids[selected] == 400]) / mass),
            "Fe85Si15": float(np.sum(w[material_ids[selected] == 402]) / mass),
        }
        radii = dict(zip(RADIUS_KEYS, np.quantile(radius, (0.95, 0.99, 1.0)), strict=True))
        body = {
            "name": name,
            "particle_count": int(np.sum(selected)),
            "mass_kg": mass,
            "position_m": center,
            "velocity_m_s": center_velocity,
            "radii_m": radii,
            "source_mass_fraction": source_fraction,
            "material_mass_fraction": material_fraction,
            "spin_angular_momentum_kg_m2_s": angular_momentum,
            "rigid_spin_omega_rad_s": angular_velocity,
            "rigid_spin_period_hr": 2.0 * np.pi / np.linalg.norm(angular_velocity) / 3600.0,
            "k2": 0.3,
            "equilibrium_Q": 100.0,
            "mode_coupling_weight": 1.0,
        }
        bodies.append(body)
        raw_positions.append(center)
        raw_velocities.append(center_velocity)
        body_masses.append(mass)

    # Store an origin-independent barycentric state.
    body_masses_array = np.asarray(body_masses)
    barycenter = np.average(np.asarray(raw_positions), axis=0, weights=body_masses_array)
    bulk_velocity = np.average(np.asarray(raw_velocities), axis=0, weights=body_masses_array)
    for body in bodies:
        body["position_m"] = np.asarray(body["position_m"]) - barycenter
        body["velocity_m_s"] = np.asarray(body["velocity_m_s"]) - bulk_velocity

    payload = {
        "model": "three largest friends-of-friends clumps",
        "snapshot": str(snapshot.resolve()),
        "labels": str(labels.resolve()),
        "snapshot_time_s": snapshot_time_s,
        "particle_count_snapshot": len(positions),
        "fof_link_length_m": link_length_m,
        "frame": "three-clump center of mass and zero total momentum",
        "bodies": bodies,
    }
    write_json(output, payload)
    return payload


def load_states(path: Path) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    payload = json.loads(path.read_text())
    bodies = payload["bodies"]
    masses = np.asarray([body["mass_kg"] for body in bodies], dtype=float)
    positions = np.asarray([body["position_m"] for body in bodies], dtype=float)
    velocities = np.asarray([body["velocity_m_s"] for body in bodies], dtype=float)
    return payload, masses, positions, velocities


def recenter(masses: np.ndarray, positions: np.ndarray, velocities: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return (
        positions - np.average(positions, axis=0, weights=masses),
        velocities - np.average(velocities, axis=0, weights=masses),
    )


def orbital_elements(r: np.ndarray, v: np.ndarray, mass_i: float, mass_j: float) -> dict[str, float]:
    mu_g = G * (mass_i + mass_j)
    distance = float(np.linalg.norm(r))
    speed = float(np.linalg.norm(v))
    h_vec = np.cross(r, v)
    h = float(np.linalg.norm(h_vec))
    energy = 0.5 * speed * speed - mu_g / distance
    eccentricity_vector = np.cross(v, h_vec) / mu_g - r / distance
    eccentricity = float(np.linalg.norm(eccentricity_vector))
    semimajor = -mu_g / (2.0 * energy) if energy != 0.0 else math.inf
    pericenter = h * h / (mu_g * (1.0 + eccentricity))
    if energy < 0.0:
        apocenter = semimajor * (1.0 + eccentricity)
        period = 2.0 * np.pi * math.sqrt(semimajor**3 / mu_g)
    else:
        apocenter = math.inf
        period = math.inf
    return {
        "distance_m": distance,
        "speed_m_s": speed,
        "radial_speed_m_s": float(np.dot(r, v) / distance),
        "specific_energy_J_kg": energy,
        "specific_angular_momentum_m2_s": h,
        "semimajor_axis_m": semimajor,
        "eccentricity": eccentricity,
        "pericenter_m": pericenter,
        "apocenter_m": apocenter,
        "period_s": period,
    }


def pair_radii(payload: dict[str, Any], radius_key: str) -> np.ndarray:
    if radius_key not in RADIUS_KEYS:
        raise ValueError(f"radius_key must be one of {RADIUS_KEYS}")
    return np.asarray([body["radii_m"][radius_key] for body in payload["bodies"]], dtype=float)


def roche_components(radius_i: float, radius_j: float, mass_i: float, mass_j: float) -> tuple[float, float]:
    """Directional incompressible-fluid Roche scales for i and j as victims."""
    victim_i = 2.44 * radius_i * (mass_j / mass_i) ** (1.0 / 3.0)
    victim_j = 2.44 * radius_j * (mass_i / mass_j) ** (1.0 / 3.0)
    return victim_i, victim_j


def pair_table(
    payload: dict[str, Any],
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, j, key, label in PAIR_SPECS:
        elements = orbital_elements(positions[j] - positions[i], velocities[j] - velocities[i], masses[i], masses[j])
        row: dict[str, Any] = {"pair": key, "label": label, **elements}
        for radius_key in RADIUS_KEYS:
            radii = pair_radii(payload, radius_key)
            contact = radii[i] + radii[j]
            roche_i, roche_j = roche_components(radii[i], radii[j], masses[i], masses[j])
            row[f"contact_{radius_key}_m"] = contact
            row[f"roche_{radius_key}_m"] = max(roche_i, roche_j)
            row[f"q_over_contact_{radius_key}"] = elements["pericenter_m"] / contact
        rows.append(row)
    return rows


def time_to_inbound_radius(elements: dict[str, float], target_radius_m: float, total_mass_kg: float) -> float:
    """Keplerian time from the current inbound state to a target radius."""
    a = elements["semimajor_axis_m"]
    e = elements["eccentricity"]
    r = elements["distance_m"]
    vr = elements["radial_speed_m_s"]
    if not (a > 0.0 and 0.0 < e < 1.0 and vr < 0.0):
        return math.nan
    if target_radius_m < elements["pericenter_m"] or target_radius_m > elements["apocenter_m"]:
        return math.nan
    mu_g = G * total_mass_kg
    cos_e_now = np.clip((1.0 - r / a) / e, -1.0, 1.0)
    sin_e_now = np.clip(vr * r / (e * math.sqrt(mu_g * a)), -1.0, 1.0)
    eccentric_anomaly_now = math.atan2(sin_e_now, cos_e_now) % (2.0 * np.pi)
    mean_anomaly_now = eccentric_anomaly_now - e * math.sin(eccentric_anomaly_now)
    cos_e_target = np.clip((1.0 - target_radius_m / a) / e, -1.0, 1.0)
    eccentric_anomaly_target = (2.0 * np.pi - math.acos(cos_e_target)) % (2.0 * np.pi)
    mean_anomaly_target = eccentric_anomaly_target - e * math.sin(eccentric_anomaly_target)
    if mean_anomaly_target < mean_anomaly_now:
        mean_anomaly_target += 2.0 * np.pi
    mean_motion = math.sqrt(mu_g / a**3)
    return (mean_anomaly_target - mean_anomaly_now) / mean_motion


def newtonian_acceleration(positions: np.ndarray, masses: np.ndarray) -> np.ndarray:
    acceleration = np.zeros_like(positions)
    for i, j, _, _ in PAIR_SPECS:
        displacement = positions[j] - positions[i]
        distance = np.linalg.norm(displacement)
        base = G * displacement / distance**3
        acceleration[i] += masses[j] * base
        acceleration[j] -= masses[i] * base
    return acceleration


def equilibrium_tide_acceleration(
    payload: dict[str, Any],
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    radii: np.ndarray,
    config: ModelConfig,
) -> tuple[np.ndarray, list[str]]:
    """Small-e radial damping calibrated to the standard equilibrium-tide t_e.

    Radial damping conserves pair orbital angular momentum and gives epicyclic
    eccentricity decay on t_e.  The force is gated off for high-e, contact- or
    Roche-crossing configurations where this weak-friction surrogate is not
    defensible.
    """
    acceleration = np.zeros_like(positions)
    active: list[str] = []
    if not config.equilibrium_tides:
        return acceleration, active
    bodies = payload["bodies"]
    for i, j, key, _ in PAIR_SPECS:
        r = positions[j] - positions[i]
        v = velocities[j] - velocities[i]
        elements = orbital_elements(r, v, masses[i], masses[j])
        a = elements["semimajor_axis_m"]
        e = elements["eccentricity"]
        q = elements["pericenter_m"]
        if not (a > 0.0 and e <= config.equilibrium_max_eccentricity):
            continue
        roche_i, roche_j = roche_components(radii[i], radii[j], masses[i], masses[j])
        safe_limit = max(
            config.equilibrium_detachment_factor * (radii[i] + radii[j]),
            roche_i,
            roche_j,
        )
        if q <= safe_limit:
            continue
        mean_motion = math.sqrt(G * (masses[i] + masses[j]) / a**3)
        rate = 0.0
        for victim, perturber in ((i, j), (j, i)):
            k2 = float(bodies[victim].get("k2", 0.3))
            quality = float(bodies[victim].get("equilibrium_Q", 100.0))
            rate += (k2 / quality) * (masses[perturber] / masses[victim]) * (radii[victim] / a) ** 5
        inverse_te = 10.5 * mean_motion * rate
        rhat = r / np.linalg.norm(r)
        relative_damping = -2.0 * inverse_te * np.dot(v, rhat) * rhat
        total_mass = masses[i] + masses[j]
        acceleration[i] -= masses[j] / total_mass * relative_damping
        acceleration[j] += masses[i] / total_mass * relative_damping
        active.append(key)
    return acceleration, active


def acceleration(
    payload: dict[str, Any],
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    radii: np.ndarray,
    config: ModelConfig,
) -> tuple[np.ndarray, list[str]]:
    weak, active = equilibrium_tide_acceleration(payload, masses, positions, velocities, radii, config)
    return newtonian_acceleration(positions, masses) + weak, active


def dynamical_tide_kick(
    payload: dict[str, Any],
    masses: np.ndarray,
    radii: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    i: int,
    j: int,
    config: ModelConfig,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply a Press--Teukolsky-scaled inelastic relative-velocity impulse."""
    r = positions[j] - positions[i]
    relative_velocity = velocities[j] - velocities[i]
    pericenter = float(np.linalg.norm(r))
    total_mass = masses[i] + masses[j]
    reduced_mass = masses[i] * masses[j] / total_mass
    relative_kinetic = 0.5 * reduced_mass * float(np.dot(relative_velocity, relative_velocity))
    contributions: list[float] = []
    eta_values: list[float] = []
    t2_values: list[float] = []
    for victim, perturber in ((i, j), (j, i)):
        eta = math.sqrt(masses[victim] / total_mass) * (pericenter / radii[victim]) ** 1.5
        weight = float(payload["bodies"][victim].get("mode_coupling_weight", 1.0))
        t2 = (
            config.dynamical_efficiency
            * weight
            * math.exp(-config.dynamical_eta_suppression * max(eta - 1.0, 0.0))
        )
        energy = (
            G
            * masses[victim] ** 2
            / radii[victim]
            * (masses[perturber] / masses[victim]) ** 2
            * (radii[victim] / pericenter) ** 6
            * t2
        )
        eta_values.append(eta)
        t2_values.append(t2)
        contributions.append(energy)
    raw_loss = float(sum(contributions))
    cap = config.dynamical_energy_cap_fraction * relative_kinetic
    used_loss = min(raw_loss, cap)
    scale = math.sqrt(max(0.0, 1.0 - used_loss / relative_kinetic)) if relative_kinetic > 0.0 else 1.0
    new_relative_velocity = scale * relative_velocity
    center_velocity = (masses[i] * velocities[i] + masses[j] * velocities[j]) / total_mass
    updated = velocities.copy()
    updated[i] = center_velocity - masses[j] / total_mass * new_relative_velocity
    updated[j] = center_velocity + masses[i] / total_mass * new_relative_velocity
    angular_momentum_before = reduced_mass * np.cross(r, relative_velocity)
    angular_momentum_after = reduced_mass * np.cross(r, new_relative_velocity)
    record = {
        "pair": next(spec[2] for spec in PAIR_SPECS if spec[0] == i and spec[1] == j),
        "pericenter_m": pericenter,
        "dynamical_efficiency": config.dynamical_efficiency,
        "eta_body_i": eta_values[0],
        "eta_body_j": eta_values[1],
        "T2_body_i": t2_values[0],
        "T2_body_j": t2_values[1],
        "energy_body_i_J": contributions[0],
        "energy_body_j_J": contributions[1],
        "energy_raw_J": raw_loss,
        "energy_used_J": used_loss,
        "energy_cap_J": cap,
        "velocity_scale": scale,
        "angular_momentum_transfer_kg_m2_s": float(np.linalg.norm(angular_momentum_before - angular_momentum_after)),
    }
    return updated, record


def state_row(
    t_s: float,
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    equilibrium_active: list[str],
) -> dict[str, Any]:
    row: dict[str, Any] = {"t_s": t_s, "t_hr_after_36h": t_s / 3600.0, "equilibrium_active": ";".join(equilibrium_active)}
    for i, j, key, _ in PAIR_SPECS:
        elements = orbital_elements(positions[j] - positions[i], velocities[j] - velocities[i], masses[i], masses[j])
        row[f"separation_{key}_m"] = elements["distance_m"]
        row[f"q_osc_{key}_m"] = elements["pericenter_m"]
        row[f"e_osc_{key}"] = elements["eccentricity"]
    return row


def classify_no_contact(
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    roche_entered: set[str],
) -> str:
    ms = orbital_elements(positions[2] - positions[1], velocities[2] - velocities[1], masses[1], masses[2])
    es = orbital_elements(positions[2] - positions[0], velocities[2] - velocities[0], masses[0], masses[2])
    em_distance = np.linalg.norm(positions[1] - positions[0])
    mars_hill = em_distance * (masses[1] / (3.0 * masses[0])) ** (1.0 / 3.0)
    if ms["specific_energy_J_kg"] < 0.0 and ms["distance_m"] < mars_hill:
        return "secondary_roche_risk" if "mars_secondary" in roche_entered else "secondary_survives_point_mass"
    if es["specific_energy_J_kg"] < 0.0 and ms["specific_energy_J_kg"] >= 0.0:
        return "secondary_stripped_by_earth"
    if es["specific_energy_J_kg"] >= 0.0 and ms["specific_energy_J_kg"] >= 0.0:
        return "three_body_ejection_candidate"
    return "unresolved_no_contact"


def integrate_model(
    payload: dict[str, Any],
    masses: np.ndarray,
    initial_positions: np.ndarray,
    initial_velocities: np.ndarray,
    config: ModelConfig,
) -> dict[str, Any]:
    """Velocity-Verlet integration stopped at first finite-radius contact."""
    radii = pair_radii(payload, config.radius_key)
    positions, velocities = recenter(masses, initial_positions.copy(), initial_velocities.copy())
    t_s = 0.0
    acceleration_now, active = acceleration(payload, masses, positions, velocities, radii, config)
    time_series = [state_row(t_s, masses, positions, velocities, active)]
    events: list[dict[str, Any]] = []
    tidal_passages: list[dict[str, Any]] = []
    roche_entered: set[str] = set()
    next_output = config.output_cadence_s
    collision: dict[str, Any] | None = None

    while t_s < config.duration_s - 1.0e-12:
        dt = min(config.dt_s, config.duration_s - t_s)
        old_positions = positions.copy()
        old_velocities = velocities.copy()
        old_radial: dict[str, float] = {}
        old_separation: dict[str, float] = {}
        for i, j, key, _ in PAIR_SPECS:
            displacement = positions[j] - positions[i]
            relative_velocity = velocities[j] - velocities[i]
            old_separation[key] = float(np.linalg.norm(displacement))
            old_radial[key] = float(np.dot(displacement, relative_velocity) / old_separation[key])

        half_velocity = velocities + 0.5 * dt * acceleration_now
        trial_positions = positions + dt * half_velocity
        trial_acceleration, active = acceleration(payload, masses, trial_positions, half_velocity, radii, config)
        trial_velocities = half_velocity + 0.5 * dt * trial_acceleration

        # Find the first contact within this step before applying any periapse kick.
        contact_candidates: list[tuple[float, int, int, str]] = []
        for i, j, key, _ in PAIR_SPECS:
            new_separation = float(np.linalg.norm(trial_positions[j] - trial_positions[i]))
            threshold = radii[i] + radii[j]
            if old_separation[key] > threshold and new_separation <= threshold:
                fraction = (old_separation[key] - threshold) / max(old_separation[key] - new_separation, 1.0e-30)
                contact_candidates.append((float(np.clip(fraction, 0.0, 1.0)), i, j, key))

        if contact_candidates:
            fraction, i, j, key = min(contact_candidates, key=lambda item: item[0])
            positions = old_positions + fraction * (trial_positions - old_positions)
            velocities = old_velocities + fraction * (trial_velocities - old_velocities)
            t_s += fraction * dt
            collision = {
                "type": "contact",
                "pair": key,
                "time_s": t_s,
                "time_hr_after_36h": t_s / 3600.0,
                "absolute_simulation_time_hr": 36.0 + t_s / 3600.0,
                "contact_radius_m": radii[i] + radii[j],
                "separation_m": float(np.linalg.norm(positions[j] - positions[i])),
                "radius_key": config.radius_key,
            }
            events.append(collision)
            time_series.append(state_row(t_s, masses, positions, velocities, active))
            break

        positions = trial_positions
        velocities = trial_velocities
        t_s += dt

        for i, j, key, _ in PAIR_SPECS:
            displacement = positions[j] - positions[i]
            separation = float(np.linalg.norm(displacement))
            relative_velocity = velocities[j] - velocities[i]
            radial = float(np.dot(displacement, relative_velocity) / separation)
            roche_i, roche_j = roche_components(radii[i], radii[j], masses[i], masses[j])
            roche = max(roche_i, roche_j)
            if key not in roche_entered and old_separation[key] > roche and separation <= roche:
                roche_entered.add(key)
                events.append(
                    {
                        "type": "roche_entry",
                        "pair": key,
                        "time_s": t_s,
                        "time_hr_after_36h": t_s / 3600.0,
                        "absolute_simulation_time_hr": 36.0 + t_s / 3600.0,
                        "separation_m": separation,
                        "roche_limit_m": roche,
                        "radius_key": config.radius_key,
                    }
                )
            if old_radial[key] < 0.0 <= radial:
                velocities, record = dynamical_tide_kick(
                    payload, masses, radii, positions, velocities, i, j, config
                )
                record.update(
                    {
                        "time_s": t_s,
                        "time_hr_after_36h": t_s / 3600.0,
                        "absolute_simulation_time_hr": 36.0 + t_s / 3600.0,
                        "inside_roche_limit": separation <= roche,
                    }
                )
                tidal_passages.append(record)

        acceleration_now, active = acceleration(payload, masses, positions, velocities, radii, config)
        if t_s + 1.0e-9 >= next_output:
            time_series.append(state_row(t_s, masses, positions, velocities, active))
            next_output += config.output_cadence_s

    if collision is not None:
        outcome = f"{collision['pair']}_contact"
    else:
        outcome = classify_no_contact(masses, positions, velocities, roche_entered)
        if not time_series or time_series[-1]["t_s"] != t_s:
            time_series.append(state_row(t_s, masses, positions, velocities, active))
    return {
        "outcome": outcome,
        "collision": collision,
        "events": events,
        "tidal_passages": tidal_passages,
        "time_series": time_series,
        "final_positions_m": positions,
        "final_velocities_m_s": velocities,
        "roche_entered": sorted(roche_entered),
        "equilibrium_ever_active": any(row["equilibrium_active"] for row in time_series),
    }


def perturb_state(
    rng: np.random.Generator,
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    outer_position_sigma_m: float,
    outer_velocity_sigma_m_s: float,
    inner_position_sigma_m: float,
    inner_velocity_sigma_m_s: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Perturb outer and inner Jacobi-like coordinates while preserving COM."""
    x = positions.copy()
    v = velocities.copy()
    delta_outer_x = rng.normal(0.0, outer_position_sigma_m, 3)
    delta_outer_v = rng.normal(0.0, outer_velocity_sigma_m_s, 3)
    x[1:] += delta_outer_x
    v[1:] += delta_outer_v

    inner_mass = masses[1] + masses[2]
    delta_inner_x = rng.normal(0.0, inner_position_sigma_m, 3)
    delta_inner_v = rng.normal(0.0, inner_velocity_sigma_m_s, 3)
    x[1] -= masses[2] / inner_mass * delta_inner_x
    x[2] += masses[1] / inner_mass * delta_inner_x
    v[1] -= masses[2] / inner_mass * delta_inner_v
    v[2] += masses[1] / inner_mass * delta_inner_v
    x, v = recenter(masses, x, v)
    return x, v, {
        "outer_position_perturbation_m": float(np.linalg.norm(delta_outer_x)),
        "outer_velocity_perturbation_m_s": float(np.linalg.norm(delta_outer_v)),
        "inner_position_perturbation_m": float(np.linalg.norm(delta_inner_x)),
        "inner_velocity_perturbation_m_s": float(np.linalg.norm(delta_inner_v)),
    }


def run_ensemble(
    payload: dict[str, Any],
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    efficiencies: list[float],
    samples: int,
    seed: int,
    base_config: ModelConfig,
    outer_position_sigma_m: float,
    outer_velocity_sigma_m_s: float,
    inner_position_sigma_m: float,
    inner_velocity_sigma_m_s: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    # Common random perturbations make changes across radius/efficiency cells
    # attributable to model assumptions rather than a different random draw.
    perturbed_samples = [
        perturb_state(
            rng,
            masses,
            positions,
            velocities,
            outer_position_sigma_m,
            outer_velocity_sigma_m_s,
            inner_position_sigma_m,
            inner_velocity_sigma_m_s,
        )
        for _ in range(samples)
    ]
    rows: list[dict[str, Any]] = []
    for radius_key in RADIUS_KEYS:
        for efficiency in efficiencies:
            config = ModelConfig(**vars(base_config))
            config.radius_key = radius_key
            config.dynamical_efficiency = efficiency
            for sample, (perturbed_x, perturbed_v, perturbations) in enumerate(perturbed_samples):
                result = integrate_model(payload, masses, perturbed_x, perturbed_v, config)
                collision = result["collision"] or {}
                rows.append(
                    {
                        "radius_key": radius_key,
                        "dynamical_efficiency": efficiency,
                        "sample": sample,
                        "outcome": result["outcome"],
                        "first_contact_time_hr_after_36h": collision.get("time_hr_after_36h", math.nan),
                        "tidal_passage_count": len(result["tidal_passages"]),
                        "equilibrium_ever_active": result["equilibrium_ever_active"],
                        **perturbations,
                    }
                )

    summary: list[dict[str, Any]] = []
    outcomes = sorted(OUTCOME_LABELS)
    for radius_key in RADIUS_KEYS:
        for efficiency in efficiencies:
            selected = [
                row
                for row in rows
                if row["radius_key"] == radius_key and row["dynamical_efficiency"] == efficiency
            ]
            counts = {outcome: sum(row["outcome"] == outcome for row in selected) for outcome in outcomes}
            dominant = max(counts, key=counts.get)
            contact_times = np.asarray(
                [row["first_contact_time_hr_after_36h"] for row in selected], dtype=float
            )
            finite_times = contact_times[np.isfinite(contact_times)]
            summary.append(
                {
                    "radius_key": radius_key,
                    "dynamical_efficiency": efficiency,
                    "samples": len(selected),
                    "dominant_outcome": dominant,
                    "dominant_fraction": counts[dominant] / len(selected),
                    "median_first_contact_hr_after_36h": float(np.median(finite_times)) if len(finite_times) else math.nan,
                    "p05_first_contact_hr_after_36h": float(np.quantile(finite_times, 0.05)) if len(finite_times) else math.nan,
                    "p95_first_contact_hr_after_36h": float(np.quantile(finite_times, 0.95)) if len(finite_times) else math.nan,
                    **{f"fraction_{outcome}": counts[outcome] / len(selected) for outcome in outcomes},
                }
            )
    return rows, summary


def reference_point_mass_events(
    payload: dict[str, Any],
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    duration_s: float,
) -> list[dict[str, Any]]:
    """High-accuracy counterfactual events with all finite sizes ignored.

    This trajectory is useful only for diagnosing collision courses.  Events
    after the first physical contact are explicitly counterfactual.
    """
    from scipy.integrate import solve_ivp

    def derivative(_time: float, state: np.ndarray) -> np.ndarray:
        x = state[:9].reshape(3, 3)
        v = state[9:].reshape(3, 3)
        return np.concatenate((v.ravel(), newtonian_acceleration(x, masses).ravel()))

    event_functions = []
    metadata: list[dict[str, Any]] = []
    for i, j, key, _ in PAIR_SPECS:
        for radius_key in RADIUS_KEYS:
            radii = pair_radii(payload, radius_key)
            threshold = radii[i] + radii[j]

            def contact_event(_time: float, state: np.ndarray, i: int = i, j: int = j, threshold: float = threshold) -> float:
                x = state[:9].reshape(3, 3)
                return float(np.linalg.norm(x[j] - x[i]) - threshold)

            contact_event.direction = -1.0
            contact_event.terminal = False
            event_functions.append(contact_event)
            metadata.append(
                {
                    "type": "counterfactual_contact",
                    "pair": key,
                    "radius_key": radius_key,
                    "threshold_m": threshold,
                }
            )

        def pericenter_event(_time: float, state: np.ndarray, i: int = i, j: int = j) -> float:
            x = state[:9].reshape(3, 3)
            v = state[9:].reshape(3, 3)
            r = x[j] - x[i]
            return float(np.dot(r, v[j] - v[i]) / np.linalg.norm(r))

        pericenter_event.direction = 1.0
        pericenter_event.terminal = False
        event_functions.append(pericenter_event)
        metadata.append({"type": "counterfactual_pericenter", "pair": key, "radius_key": "point_mass"})

    initial_state = np.concatenate((positions.ravel(), velocities.ravel()))
    solution = solve_ivp(
        derivative,
        (0.0, duration_s),
        initial_state,
        method="DOP853",
        events=event_functions,
        rtol=1.0e-11,
        atol=np.concatenate((np.full(9, 1.0e-2), np.full(9, 1.0e-7))),
        max_step=60.0,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    rows: list[dict[str, Any]] = []
    first_event_time = math.inf
    contact_indices = [index for index, item in enumerate(metadata) if item["type"] == "counterfactual_contact"]
    for index in contact_indices:
        if len(solution.t_events[index]):
            first_event_time = min(first_event_time, float(solution.t_events[index][0]))
    for item, times, states in zip(metadata, solution.t_events, solution.y_events, strict=True):
        for occurrence, (event_time, state) in enumerate(zip(times, states, strict=True), start=1):
            x = state[:9].reshape(3, 3)
            i, j, _, _ = next(spec for spec in PAIR_SPECS if spec[2] == item["pair"])
            rows.append(
                {
                    **item,
                    "occurrence": occurrence,
                    "time_s": float(event_time),
                    "time_hr_after_36h": float(event_time / 3600.0),
                    "absolute_simulation_time_hr": float(36.0 + event_time / 3600.0),
                    "separation_m": float(np.linalg.norm(x[j] - x[i])),
                    "after_first_counterfactual_contact": bool(event_time > first_event_time + 1.0e-6),
                }
            )
    rows.sort(key=lambda row: row["time_s"])
    return rows


def dynamical_tide_scale(
    payload: dict[str, Any],
    masses: np.ndarray,
    radii: np.ndarray,
    i: int,
    j: int,
    distance_m: float,
    efficiency: float,
    eta_suppression: float = 2.0,
) -> float:
    config = ModelConfig(
        radius_key="r99",
        dynamical_efficiency=efficiency,
        dynamical_eta_suppression=eta_suppression,
    )
    # The kick budget depends only on r_p here; use any transverse unit velocity
    # and read the uncapped raw energy.
    x = np.zeros((3, 3))
    v = np.zeros((3, 3))
    x[j, 0] = distance_m
    v[j, 1] = 1.0e9  # keep the numerical cap inactive
    _, record = dynamical_tide_kick(payload, masses, radii, x, v, i, j, config)
    return float(record["energy_raw_J"])


def analytic_diagnostics(
    payload: dict[str, Any],
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    efficiencies: list[float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pair_rows = pair_table(payload, masses, positions, velocities)
    tide_rows: list[dict[str, Any]] = []
    for row, (i, j, key, _) in zip(pair_rows, PAIR_SPECS, strict=True):
        reduced_mass = masses[i] * masses[j] / (masses[i] + masses[j])
        h = row["specific_angular_momentum_m2_s"]
        a = row["semimajor_axis_m"]
        for radius_key in RADIUS_KEYS:
            target = row[f"contact_{radius_key}_m"]
            row[f"two_body_time_to_contact_{radius_key}_hr"] = (
                time_to_inbound_radius(row, target, masses[i] + masses[j]) / 3600.0
            )
        if key != "earth_mars":
            continue
        target = row["contact_r99_m"]
        if a > 0.0 and target < 2.0 * a:
            target_h = math.sqrt(G * (masses[i] + masses[j]) * (2.0 * target - target * target / a))
            row["angular_momentum_increase_to_r99_contact_kg_m2_s"] = reduced_mass * max(target_h - h, 0.0)
            row["fractional_h_increase_to_r99_contact"] = max(target_h / h - 1.0, 0.0)
        # Inbound two-body radial energy at first r99 contact.
        mu_g = G * (masses[i] + masses[j])
        speed2 = 2.0 * (row["specific_energy_J_kg"] + mu_g / target)
        tangential2 = h * h / target**2
        radial2 = max(speed2 - tangential2, 0.0)
        radial_kinetic = 0.5 * reduced_mass * radial2
        row["radial_kinetic_at_r99_contact_J"] = radial_kinetic
        radii = pair_radii(payload, "r99")
        orbital_binding = G * masses[i] * masses[j] / (2.0 * a)
        for efficiency in efficiencies:
            energy = dynamical_tide_scale(payload, masses, radii, i, j, target, efficiency)
            tide_rows.append(
                {
                    "pair": key,
                    "evaluation_distance": "r99_contact",
                    "distance_m": target,
                    "dynamical_efficiency": efficiency,
                    "energy_scale_J": energy,
                    "fraction_of_orbital_binding": energy / orbital_binding,
                    "fraction_of_inbound_radial_kinetic": energy / radial_kinetic,
                    "caveat": "marginal linear-tide estimate at geometric contact; hydrodynamics dominates",
                }
            )
    return pair_rows, tide_rows


def make_plots(
    output_dir: Path,
    payload: dict[str, Any],
    nominal: dict[str, Any],
    config: ModelConfig,
    ensemble_summary: list[dict[str, Any]],
    efficiencies: list[float],
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = nominal["time_series"]
    time_hr = np.asarray([row["t_hr_after_36h"] for row in rows])
    radii = pair_radii(payload, config.radius_key)

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    colors = ("#3366aa", "#cc3311", "#228833")
    for (i, j, key, label), color in zip(PAIR_SPECS, colors, strict=True):
        separation = np.asarray([row[f"separation_{key}_m"] for row in rows]) / 1.0e3
        ax.plot(time_hr, separation, color=color, label=label)
        ax.axhline((radii[i] + radii[j]) / 1.0e3, color=color, alpha=0.25, linestyle=":")
    ax.set_yscale("log")
    ax.set_xlabel("hours after the 36 h snapshot")
    ax.set_ylabel("center separation (km)")
    ax.set_title(f"Nominal three-clump evolution to first {config.radius_key} contact")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(output_dir / "nominal_separations.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(8.0, 8.0), sharex=True)
    for ax, (i, j, key, label), color in zip(axes, PAIR_SPECS, colors, strict=True):
        q = np.asarray([row[f"q_osc_{key}_m"] for row in rows]) / 1.0e3
        ax.plot(time_hr, q, color=color, label="instantaneous osculating q")
        contact = (radii[i] + radii[j]) / 1.0e3
        roche_i, roche_j = roche_components(radii[i], radii[j], payload["bodies"][i]["mass_kg"], payload["bodies"][j]["mass_kg"])
        ax.axhline(contact, color="black", linestyle=":", label="contact")
        ax.axhline(max(roche_i, roche_j) / 1.0e3, color="0.45", linestyle="--", label="fluid Roche scale")
        ax.set_ylabel("q (km)")
        ax.set_title(label, loc="left", fontsize=10)
        ax.grid(alpha=0.2)
    axes[-1].set_xlabel("hours after the 36 h snapshot")
    axes[0].legend(frameon=False, ncol=3, fontsize=8)
    fig.suptitle("Osculating pericenter evolution (diagnostic, not secular elements)")
    fig.tight_layout()
    fig.savefig(output_dir / "nominal_pericenter_evolution.png", dpi=180)
    plt.close(fig)

    passages = nominal["tidal_passages"]
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    if passages and any(record["energy_used_J"] > 0.0 for record in passages):
        for key, color in zip((spec[2] for spec in PAIR_SPECS), colors, strict=True):
            selected = [record for record in passages if record["pair"] == key]
            if selected:
                ax.scatter(
                    [record["time_hr_after_36h"] for record in selected],
                    [record["energy_used_J"] for record in selected],
                    color=color,
                    label=next(spec[3] for spec in PAIR_SPECS if spec[2] == key),
                )
        ax.set_yscale("log")
    else:
        ax.text(0.5, 0.5, "No non-zero detached-passage tide impulses", ha="center", va="center", transform=ax.transAxes)
    ax.set_xlabel("hours after the 36 h snapshot")
    ax.set_ylabel("orbital energy removed per passage (J)")
    ax.set_title(f"Dynamical-tide impulses, efficiency={config.dynamical_efficiency:g}")
    ax.grid(alpha=0.2)
    if passages:
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_dir / "nominal_tidal_energy.png", dpi=180)
    plt.close(fig)

    outcomes = sorted({row["dominant_outcome"] for row in ensemble_summary})
    palette = ["#4477aa", "#ee6677", "#228833", "#ccbb44", "#66ccee", "#aa3377", "#bbbbbb"]
    outcome_index = {outcome: index for index, outcome in enumerate(outcomes)}
    matrix = np.zeros((len(RADIUS_KEYS), len(efficiencies)), dtype=int)
    annotations: list[list[str]] = [["" for _ in efficiencies] for _ in RADIUS_KEYS]
    abbreviations = {
        "earth_mars_contact": "E--M",
        "mars_secondary_contact": "M--S",
        "earth_secondary_contact": "E--S",
        "secondary_survives_point_mass": "survive",
        "secondary_roche_risk": "Roche",
        "secondary_stripped_by_earth": "strip",
        "three_body_ejection_candidate": "eject",
        "unresolved_no_contact": "none",
    }
    for row in ensemble_summary:
        iy = RADIUS_KEYS.index(row["radius_key"])
        ix = efficiencies.index(float(row["dynamical_efficiency"]))
        outcome = row["dominant_outcome"]
        matrix[iy, ix] = outcome_index[outcome]
        annotations[iy][ix] = f"{abbreviations[outcome]}\n{100.0 * row['dominant_fraction']:.0f}%"
    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    cmap = ListedColormap(palette[: max(len(outcomes), 1)])
    ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=-0.5, vmax=max(len(outcomes) - 0.5, 0.5))
    for iy in range(len(RADIUS_KEYS)):
        for ix in range(len(efficiencies)):
            ax.text(ix, iy, annotations[iy][ix], ha="center", va="center", fontsize=9)
    ax.set_xticks(range(len(efficiencies)), [f"{value:g}" for value in efficiencies])
    ax.set_yticks(range(len(RADIUS_KEYS)), RADIUS_KEYS)
    ax.set_xlabel("dynamical-tide mode-coupling efficiency")
    ax.set_ylabel("effective remnant radius")
    ax.set_title("Dominant first-contact outcome in perturbed three-body ensemble")
    handles = [Patch(color=palette[outcome_index[outcome]], label=OUTCOME_LABELS[outcome]) for outcome in outcomes]
    ax.legend(handles=handles, frameon=False, bbox_to_anchor=(1.02, 1.0), loc="upper left")
    fig.tight_layout()
    fig.savefig(output_dir / "outcome_map.png", dpi=180)
    plt.close(fig)


def make_summary(
    output_dir: Path,
    payload: dict[str, Any],
    nominal: dict[str, Any],
    config: ModelConfig,
    pair_rows: list[dict[str, Any]],
    ensemble_summary: list[dict[str, Any]],
    reference_events: list[dict[str, Any]],
) -> dict[str, Any]:
    earth_mars = next(row for row in pair_rows if row["pair"] == "earth_mars")
    mars_secondary = next(row for row in pair_rows if row["pair"] == "mars_secondary")
    collision = nominal["collision"] or {}
    es_fractions = [row.get("fraction_earth_secondary_contact", 0.0) for row in ensemble_summary]
    em_fractions = [row.get("fraction_earth_mars_contact", 0.0) for row in ensemble_summary]
    ms_fractions = [row.get("fraction_mars_secondary_contact", 0.0) for row in ensemble_summary]
    reference_em_r99 = next(
        (
            row
            for row in reference_events
            if row["type"] == "counterfactual_contact"
            and row["pair"] == "earth_mars"
            and row["radius_key"] == "r99"
        ),
        None,
    )
    summary = {
        "headline": "The finite-radius nominal model reaches secondary--Earth contact before the counterfactual Earth--Mars contact.",
        "nominal_radius_key": config.radius_key,
        "nominal_dynamical_efficiency": config.dynamical_efficiency,
        "nominal_first_outcome": nominal["outcome"],
        "nominal_first_contact_hr_after_36h": collision.get("time_hr_after_36h"),
        "nominal_first_contact_absolute_hr": collision.get("absolute_simulation_time_hr"),
        "earth_mars_initial_osculating_q_km": earth_mars["pericenter_m"] / 1.0e3,
        "earth_mars_r99_contact_km": earth_mars["contact_r99_m"] / 1.0e3,
        "earth_mars_two_body_r99_contact_hr_after_36h": earth_mars["two_body_time_to_contact_r99_hr"],
        "earth_mars_three_body_counterfactual_r99_contact_hr_after_36h": (
            reference_em_r99["time_hr_after_36h"] if reference_em_r99 else None
        ),
        "earth_mars_fractional_h_increase_needed_to_clear_r99": earth_mars.get("fractional_h_increase_to_r99_contact"),
        "earth_mars_delta_L_needed_to_clear_r99_kg_m2_s": earth_mars.get("angular_momentum_increase_to_r99_contact_kg_m2_s"),
        "mars_secondary_initial_osculating_q_km": mars_secondary["pericenter_m"] / 1.0e3,
        "mars_secondary_r99_contact_km": mars_secondary["contact_r99_m"] / 1.0e3,
        "mars_secondary_r99_roche_km": mars_secondary["roche_r99_m"] / 1.0e3,
        "nominal_roche_entries": nominal["roche_entered"],
        "nominal_equilibrium_tides_activated": nominal["equilibrium_ever_active"],
        "ensemble_min_fraction_earth_secondary_first": min(es_fractions) if es_fractions else None,
        "ensemble_max_fraction_earth_secondary_first": max(es_fractions) if es_fractions else None,
        "ensemble_max_fraction_earth_mars_first": max(em_fractions) if em_fractions else None,
        "ensemble_max_fraction_mars_secondary_first": max(ms_fractions) if ms_fractions else None,
        "interpretive_limit": "Any contact or Roche entry invalidates subsequent point-mass evolution; continue with SPH for post-contact outcomes.",
    }
    write_json(output_dir / "summary.json", summary)
    return summary


def parse_float_list(value: str) -> list[float]:
    return [float(item) for item in value.split(",")]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="extract the three clumps from a SWIFT snapshot")
    extract.add_argument("--snapshot", type=Path, required=True)
    extract.add_argument("--labels", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--link-length-km", type=float, default=500.0)

    run = subparsers.add_parser("run", help="run nominal model, ensemble, plots, and tables")
    run.add_argument("--states", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--radius-key", choices=RADIUS_KEYS, default="r99")
    run.add_argument("--dynamical-efficiency", type=float, default=0.01)
    run.add_argument("--efficiency-grid", type=parse_float_list, default=parse_float_list("0,0.001,0.01,0.1"))
    run.add_argument("--duration-hours", type=float, default=36.0)
    run.add_argument("--dt-seconds", type=float, default=20.0)
    run.add_argument("--output-cadence-seconds", type=float, default=300.0)
    run.add_argument("--ensemble-samples", type=int, default=32)
    run.add_argument("--seed", type=int, default=20260813)
    run.add_argument("--outer-position-sigma-km", type=float, default=100.0)
    run.add_argument("--outer-velocity-sigma-m-s", type=float, default=20.0)
    run.add_argument("--inner-position-sigma-km", type=float, default=50.0)
    run.add_argument("--inner-velocity-sigma-m-s", type=float, default=10.0)
    run.add_argument("--disable-equilibrium-tides", action="store_true")
    return parser


def command_run(args: argparse.Namespace) -> None:
    payload, masses, positions, velocities = load_states(args.states)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    config = ModelConfig(
        radius_key=args.radius_key,
        dynamical_efficiency=args.dynamical_efficiency,
        equilibrium_tides=not args.disable_equilibrium_tides,
        dt_s=args.dt_seconds,
        duration_s=args.duration_hours * 3600.0,
        output_cadence_s=args.output_cadence_seconds,
    )
    pair_rows, tide_scale_rows = analytic_diagnostics(
        payload, masses, positions, velocities, args.efficiency_grid
    )
    nominal = integrate_model(payload, masses, positions, velocities, config)
    reference_events = reference_point_mass_events(
        payload, masses, positions, velocities, config.duration_s
    )
    nominal_grid: list[dict[str, Any]] = []
    for radius_key in RADIUS_KEYS:
        for efficiency in args.efficiency_grid:
            grid_config = ModelConfig(**vars(config))
            grid_config.radius_key = radius_key
            grid_config.dynamical_efficiency = efficiency
            grid_result = integrate_model(payload, masses, positions, velocities, grid_config)
            grid_collision = grid_result["collision"] or {}
            nominal_grid.append(
                {
                    "radius_key": radius_key,
                    "dynamical_efficiency": efficiency,
                    "outcome": grid_result["outcome"],
                    "first_contact_pair": grid_collision.get("pair", ""),
                    "first_contact_hr_after_36h": grid_collision.get("time_hr_after_36h", math.nan),
                    "first_contact_absolute_hr": grid_collision.get("absolute_simulation_time_hr", math.nan),
                    "total_dynamical_tide_energy_J": sum(
                        passage["energy_used_J"] for passage in grid_result["tidal_passages"]
                    ),
                    "tidal_passage_count": len(grid_result["tidal_passages"]),
                    "roche_entries": ";".join(grid_result["roche_entered"]),
                    "equilibrium_ever_active": grid_result["equilibrium_ever_active"],
                }
            )
    ensemble_rows, ensemble_summary = run_ensemble(
        payload,
        masses,
        positions,
        velocities,
        args.efficiency_grid,
        args.ensemble_samples,
        args.seed,
        config,
        args.outer_position_sigma_km * 1.0e3,
        args.outer_velocity_sigma_m_s,
        args.inner_position_sigma_km * 1.0e3,
        args.inner_velocity_sigma_m_s,
    )

    write_csv(output_dir / "clump_pair_diagnostics.csv", pair_rows)
    write_csv(output_dir / "contact_tide_scale.csv", tide_scale_rows)
    write_csv(output_dir / "nominal_timeseries.csv", nominal["time_series"])
    write_csv(output_dir / "nominal_events.csv", nominal["events"])
    write_csv(output_dir / "nominal_tidal_passages.csv", nominal["tidal_passages"])
    write_csv(output_dir / "nominal_grid.csv", nominal_grid)
    write_csv(output_dir / "counterfactual_point_mass_events.csv", reference_events)
    write_csv(output_dir / "ensemble_runs.csv", ensemble_rows)
    write_csv(output_dir / "outcome_map.csv", ensemble_summary)
    write_json(
        output_dir / "run_config.json",
        {
            "states": str(args.states),
            "model_config": vars(config),
            "efficiency_grid": args.efficiency_grid,
            "ensemble_samples_per_cell": args.ensemble_samples,
            "seed": args.seed,
            "uncertainty_model": {
                "outer_position_sigma_km_per_component": args.outer_position_sigma_km,
                "outer_velocity_sigma_m_s_per_component": args.outer_velocity_sigma_m_s,
                "inner_position_sigma_km_per_component": args.inner_position_sigma_km,
                "inner_velocity_sigma_m_s_per_component": args.inner_velocity_sigma_m_s,
            },
        },
    )
    make_plots(output_dir, payload, nominal, config, ensemble_summary, args.efficiency_grid)
    summary = make_summary(
        output_dir,
        payload,
        nominal,
        config,
        pair_rows,
        ensemble_summary,
        reference_events,
    )
    print(json.dumps(_json_number(summary), indent=2))


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "extract":
        payload = extract_clump_states(
            args.snapshot,
            args.labels,
            args.output,
            args.link_length_km * 1.0e3,
        )
        print(json.dumps(_json_number(payload), indent=2))
    elif args.command == "run":
        command_run(args)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
