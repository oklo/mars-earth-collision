# Reproducibility Manifest

Generated/updated: 2026-07-13 local time

## Builds
- Fixed-entropy settling SWIFT: `/Users/greglaughlin/Projects/earth-mars-swift/swift/swift`
  - git revision: `v2026.04-55-g4ee5b667c`
  - configure: `CC=clang --disable-compiler-warnings --disable-mpi --disable-hand-vec --disable-vec --with-hydro=planetary --with-equation-of-state=planetary --enable-planetary-fixed-entropy --with-kernel=wendland-C2 --with-hdf5=/Users/greglaughlin/Projects/earth-mars-swift/.conda-swift/bin/h5cc`
- Entropy-evolving impact SWIFT: `/Users/greglaughlin/Projects/earth-mars-swift/swift-impact/swift`
  - git revision: `v2026.04-55-g4ee5b667c`
  - configure: `CC=clang --disable-compiler-warnings --disable-mpi --disable-hand-vec --disable-vec --with-hydro=planetary --with-equation-of-state=planetary --with-kernel=wendland-C2 --with-hdf5=/Users/greglaughlin/Projects/earth-mars-swift/.conda-swift/bin/h5cc`

## Low-Resolution Run Products
- `earth_unrelaxed_n05000.hdf5` size=472976 sha256=10f0c26f135e5502924bdb7328b27a1bd458046353709f65b0aef21f09bda2f4
- `mars_unrelaxed_n05000.hdf5` size=81800 sha256=c21a24449b64099f78702b5e8357b19cab8504cb3e9495a733d7f3857a012381
- `snapshots_relax_earth/earth_relax_n05000_0004.hdf5` size=772252 sha256=97e576b971f344d61dea5f2e63aa02a70a104c1c516a091973ec8ce241fbbe80
- `snapshots_relax_mars/mars_relax_n05000_0004.hdf5` size=265980 sha256=af2ab5417955bf2c97b216caab714baaf1e7bc1aa8a0e9b9048cd8f61ddfebc8
- `mars_earth_grazing_settled_n05000.hdf5` size=518956 sha256=170196e8817f7fb98bd518ca9a3ab8b76dd390a36ea3be9c24847664e4d32498
- `mars_earth_grazing_settled_n05000_labels.hdf5` size=230822 sha256=c6b0d4161ee3ed76c6a2b549a010a41935ae851b9282bbb198f4bd6f44e317fc
- `mars_earth_grazing_settled_n05000_preview.png` size=382709 sha256=2fe80951da4981a59cde32f0bfd490fa52dbd032ae607bc055db905025926b0c

## Workflow Files
- `make_mars_earth_ic.py` sha256=1a5071ac92643c41cf8a3f8274f3b23abf84971083b795c8a89db8c4bd0d8864
- `assemble_settled_impact.py` sha256=f257ee0aa216c9eea4b9a00f6616780ff413a9963a28f09c104da6d5d41010ff
- `analyze_body_snapshot.py` sha256=25b44560f16fdb8d0e8b3b08954a46ebef5607fa86c2e108b3ab0f0e1b6116ae
- `plot_initial_conditions.py` sha256=e5af61aca533d319de4558e5b19dba1701212ad7b2099eb5b71fb2c82e7b2d5b
- `earth_relax_n05000.yml` sha256=cbcba54e078e97843ade51e90847fde7f2371523bce61e0a234f1bd76877a9da
- `mars_relax_n05000.yml` sha256=cbd108f415e9d1fc6f765560db2fcd779c993192d6d2938020e693c9cd1b7e41
- `mars_earth_grazing_settled_smoke.yml` sha256=0c65a12e3b296f0a371c0d47e3d1f5fe5ba994259664f37957c84516d1a48c53
- `mars_earth_grazing_settled_4h.yml` sha256=d499c10e37a78aa342ba48649dd77bfe3be4718a7a86a5e19d0dc24119f52251
- `run_relax_lowres.sh` sha256=cad1101b21d24450ee440762a39faffef59a73e860cca9b7e99380c471d9cb0e
- `run_settled_smoke.sh` sha256=4572a4983be91cb699ec099dfedd3f8336303da35af27ca3cadc485b94b788f9

## EOS Tables
- `ANEOS_Fe85Si15_S20.txt` size=41487447 sha256=db28af227d7f9f8be58dac5f55581122966a8a05ee7caee035a2a02c91cf44a4
- `ANEOS_forsterite_S19.txt` size=39067522 sha256=81ca291e96262aea8f1006233a01764f96bac703d37533c65b27d7ed4013f1c7
- `ANEOS_iron_S20.txt` size=41435726 sha256=168d667ae8f74465e2ac393f7aad805c069ce39e11411bb8f9caecca83272768
- `AQUA_H20.txt` size=27604242 sha256=607522b71582ad70aad37c56d9f321c4f01d475999f833414ab37c7405cf25d2
- `CD21_HHe.txt` size=1784977 sha256=8dccb8145c9b9fde943c79037b58711fa178284fd4b2cd8278a3be63bef6af1e
- `CMS19_H.txt` size=2080764 sha256=ffdec421849fd4218af5dc4f30ac2ce54d10f89b3cf9705a49d47f986c7ff454
- `CMS19_He.txt` size=2080787 sha256=3d759b563ba0c4d511370cf612d510c3c56120515f04d09427ed60e995cbc255
- `HM80_HHe.txt` size=260832 sha256=c1ded254602de027acf56707d3cd2277f5c9012b17f8fe150ef229bad66dcd75
- `HM80_ice.txt` size=260831 sha256=0fdb308fa95221a052c5375a42a7e8f02949505414be8f1fa0567ffd5e7ac52b
- `HM80_rock.txt` size=260832 sha256=e85b9c87374615dd26e4f622699f23fe911691c2bd6fe8f79df7f64f1da7109c
- `SESAME_basalt_7530.txt` size=162749 sha256=6db0e72cfdfdaf217ddf71fdb85f285cf0c0069695ec4cb2f05dd67b4af7d483
- `SESAME_iron_2140.txt` size=144337 sha256=e9d3b1abd8bd09f72c846cbcab786dfb99fd72930db4b60fe1dc8c4ca4dba3a1
- `SESAME_water_7154.txt` size=151260 sha256=279a7f6cf26b580fa768a61c4d5248249f924a3156c757cff4458cd9fc911af6
- `SS08_water.txt` size=3669072 sha256=50cc709ca9453f5383089f46b96ce35c92b062fa0aecd7154981aadaf4e70911

## Resolution Ladder: `n20000` Completed Rung

Run command:

```bash
THREADS=12 RUN_IMPACT_4H=1 ./run_ladder_case.sh 20000
```

The requested `n_total=20000` produced 23,749 actual particles. The four-hour impact run used 49 snapshots at 300 s cadence and completed through `snapshots_settled_n20000_4h/mars_earth_grazing_settled_n20000_4h_0048.hdf5`.

Relaxed-body diagnostics:

- Earth final snapshot: `snapshots_relax_earth_n20000/earth_relax_n20000_0004.hdf5`; mass `5.95833581e24 kg`; `r_99.5 = 6.30594445e6 m`; radial velocity RMS `21.3089795 m/s`; COM offset `101.232603 m`; COM speed `1.54984882e-03 m/s`.
- Mars final snapshot: `snapshots_relax_mars_n20000/mars_relax_n20000_0004.hdf5`; mass `6.39455447e23 kg`; `r_99.5 = 3.11802703e6 m`; radial velocity RMS `4.82678974 m/s`; COM offset `723.492872 m`; COM speed `3.95690314e-02 m/s`.

Primary `n20000` checksums:

- `earth_relax_n20000.yml` sha256=85d1b22f216fb8dfc9686e0c134e1aaf1882bd91aeb61b4101b70d1873748154
- `mars_relax_n20000.yml` sha256=441d58f648587d9011d24b9fca10b81b28c7bbfa39170059c358cd83d36189ef
- `mars_earth_grazing_settled_n20000_4h.yml` sha256=9760f92290973e43e407167cca9a3cb381a2d2b3b15f46d7ef0030b6e89cd0c9
- `diagnostics_earth_n20000.txt` sha256=a3b8e94cf2cef725f1ab6b046d7061890eaf09e885e20a755c0f6a8a20d66591
- `diagnostics_mars_n20000.txt` sha256=5ea27a4044967db6de790ee9ba061a9d31ad5452afba37f00d3c8e917ac4679d
- `mars_earth_grazing_settled_n20000.hdf5` sha256=2bd027dc08c7ab8c6a4a8f2cccaad1ddb1e0cfada6dd27ee8c4dfe1301e02b43
- `mars_earth_grazing_settled_n20000_labels.hdf5` sha256=822701142a0d37ac32d5a04ce806ee57bee12186a5842a3b5c4f951d81089a6e
- `mars_earth_grazing_settled_n20000_preview.png` sha256=da8bfb7c6d34245b5442a79674512ce2812c26e0e883c25fb31b252b762ab0cd
- `snapshots_settled_n20000_4h/mars_earth_grazing_settled_n20000_4h_0000.hdf5` sha256=f153d950ab6ae2ee24c4a1224dce57e6a87e47162cd3935339576584eab02ae8
- `snapshots_settled_n20000_4h/mars_earth_grazing_settled_n20000_4h_0024.hdf5` sha256=9418aa73b4dd66eed72f352f2ced89703ae047386a958b242b6aa398c179e61f
- `snapshots_settled_n20000_4h/mars_earth_grazing_settled_n20000_4h_0048.hdf5` sha256=5fd79343c0971d460fb8c61e736783fd89297f8b2e163dcd05b91549bf73181d

Animation products:

- `mars_earth_grazing_settled_n20000_30s.mp4` sha256=a383d256a9b1083145e5ca973daa10bba74d9bd0bf220416adac0dfb27e7e706, verified by `ffprobe` as 1920x1080, 24 fps, 30.0 s, 720 frames.
- `mars_earth_grazing_settled_n20000_30s_midframe.png` sha256=6343998d457c6d2d7fb4ce4bbf75633b71a136ba7c528a61a23a83cfbbd134f7.

Additional workflow files added for the ladder:

- `make_ladder_configs.py` sha256=de80b7e29734e69ab97b804efd0818b8c7821f49325ee63c2827919b779fc7dc
- `run_ladder_case.sh` sha256=9541708a17cc12e3511b9797adc8db9c6017b4af6c99332e5027fcaf21b4e9c1
- `render_impact_animation.py` sha256=c808197e18d661517182a05359897a6430e870bdbdc210b6596d6515a03ac3b7

## Resolution Ladder: `n50000` and `n100000` Completed Rungs

Run commands:

```bash
THREADS=12 ./run_ladder_with_animation.sh 50000
THREADS=12 ./run_ladder_with_animation.sh 100000
```

Both runs used 20,000 s fixed-entropy relaxation for each body, then a 14,400 s entropy-evolving impact with snapshots every 300 s. Both completed through final snapshot index `0048` and produced 1920x1080, 24 fps, 30.0 s, 720-frame MP4 animations.

Summary:

- `n50000`: requested `n_total=50000`; actual combined particles `57089`; impact snapshot directory size about 257 MB; MP4 size about 4.3 MB.
- `n100000`: requested `n_total=100000`; actual combined particles `112486`; impact snapshot directory size about 507 MB; MP4 size about 3.0 MB.

Relaxed-body diagnostics:

- `n50000` Earth: 51,738 particles; mass `5.95849318e24 kg`; `r_99.5 = 6.37615996e6 m`; radial RMS `21.2639727 m/s`; tangential RMS `5.00424556 m/s`.
- `n50000` Mars: 5,351 particles; mass `6.39487224e23 kg`; `r_99.5 = 3.19738690e6 m`; radial RMS `8.22461788 m/s`; tangential RMS `7.12732416 m/s`.
- `n100000` Earth: 101,120 particles; mass `5.95858541e24 kg`; `r_99.5 = 6.41789842e6 m`; radial RMS `22.2765295 m/s`; tangential RMS `3.66594314 m/s`.
- `n100000` Mars: 11,366 particles; mass `6.39535791e23 kg`; `r_99.5 = 3.24292878e6 m`; radial RMS `12.5489388 m/s`; tangential RMS `4.19912617 m/s`.

Checksums:

- `run_ladder_with_animation.sh` sha256=efa6ecefe9decafb4fd2afff369724fc9b62dbe6f6c63ab30262da02ad08b82b
- `render_impact_animation.py` sha256=c808197e18d661517182a05359897a6430e870bdbdc210b6596d6515a03ac3b7
- `mars_earth_grazing_settled_n50000.hdf5` sha256=2e08634c0da275f06ab3c6d158737ff43d7a4d0ed98195612443ccadf4e27ad6
- `mars_earth_grazing_settled_n50000_labels.hdf5` sha256=dd10d314a2efd718c619e4f1124f868f343870b043c9e52d32d19b2468455f07
- `mars_earth_grazing_settled_n50000_30s.mp4` sha256=a24bcedcd090542754a4be6f45ac976436ba0ae1252a9303fab20f3b7d21c3ab
- `mars_earth_grazing_settled_n50000_30s_midframe.png` sha256=48c626ae6f434deb19af059f12b2e133e76ac3af0622592270631a437be96cd7
- `snapshots_settled_n50000_4h/mars_earth_grazing_settled_n50000_4h_0048.hdf5` sha256=db888e1ae94a2b2e352e0fc3fafcef3b3e33c0e6f229ddd6a556a42ee334afb4
- `mars_earth_grazing_settled_n100000.hdf5` sha256=6cdab3a91943373afb91aa1d415aa8bf1b990c9fafea9c732527b3e0b90133b5
- `mars_earth_grazing_settled_n100000_labels.hdf5` sha256=50a99ca6661eb44c59b4dd445cb3d2317e6ab41dd67490e6f1e1c705dba7c4fe
- `mars_earth_grazing_settled_n100000_30s.mp4` sha256=57c75612ad7ab3c67468f235e7d65493508e58a15517eb19c8964757745c5f6e
- `mars_earth_grazing_settled_n100000_30s_midframe.png` sha256=a2cfd32e9b8d27231f4138ec0d130ae5a161b320c31fb642fd2f5c69896121a6
- `snapshots_settled_n100000_4h/mars_earth_grazing_settled_n100000_4h_0048.hdf5` sha256=44911aa0c4bff5bedd070243b085d4f55b6d07d83cd5a17c1c258054206d1af0

## Refined Animation Render Pass

Renderer change: `render_impact_animation.py` now projects full 3D particle positions, draws a dim body-base layer, then draws a smaller-marker, depth-sorted, observer-facing surface layer. Earth land/ocean colors are still keyed to the existing `SurfaceClass`/continent labels, but the render palette now avoids far-side wash-through and reduces marker size at higher particle count. The refined runs used `--view-vector 0,-0.55,0.84`.

Verification: both refined MP4s were verified by `ffprobe` as 1920x1080, 24 fps, 30.0 s, 720 frames.

Checksums:

- `render_impact_animation.py` sha256=74a0dbd71adece512fa1d751debc1689e968b6437d41ed6002fbc789c81ded37
- `mars_earth_grazing_settled_n50000_30s_refined.mp4` sha256=9edddee6e7057958a81cc07cf1bb4aa3c2631b59f18ff9b032416a5435aee182
- `mars_earth_grazing_settled_n50000_30s_refined_midframe.png` sha256=a89dd8e20bb25d42e24ecd26e76bad06602040f38a59f7a5dae457939aef8b4b
- `mars_earth_grazing_settled_n100000_30s_refined.mp4` sha256=ad6e61042c4b5949311a0846a0b05c4b96a29f0e372e036e1f38c7a979f7f8c2
- `mars_earth_grazing_settled_n100000_30s_refined_midframe.png` sha256=8400623082bc698b64ae677d22f31293deeba0702bb32906e9e34fc58fd96e71
