# Changelog

Rendered by CI and committed back at the end of a release -- do not edit by
hand. Release notes also appear on the GitHub Releases page, one per tag.

## [1.0.12](https://github.com/hyperi-io/vector-vrl/compare/v1.0.11...v1.0.12) (2026-10-31)

### Bug Fixes

* declare the repo classification as oss ([#57](https://github.com/hyperi-io/vector-vrl/issues/57)) ([7fe3f4d](https://github.com/hyperi-io/vector-vrl/commit/7fe3f4dbeb4d981c1d9e4ffcffc64dfc134dad1d))
* run the Python test suites in parallel ([#56](https://github.com/hyperi-io/vector-vrl/issues/56)) ([e4ce7f4](https://github.com/hyperi-io/vector-vrl/commit/e4ce7f4206825569434e2a73bb8a89c3a4a5e06f))
* run VRL on its own stack, fail infinite floats and stream the performance run ([#58](https://github.com/hyperi-io/vector-vrl/issues/58)) ([c12f30b](https://github.com/hyperi-io/vector-vrl/commit/c12f30b2611d71eee4e1af28293e6c6bdf986bc9))
* **security:** take ctutils 0.4.5 and key the uv cache per wheel ([#50](https://github.com/hyperi-io/vector-vrl/issues/50)) ([019601b](https://github.com/hyperi-io/vector-vrl/commit/019601bedbdefcc72385a7b180935e3f9e04c4f5))
* test against Vector 0.60.0 and follow vrl 0.37 ([#55](https://github.com/hyperi-io/vector-vrl/issues/55)) ([44aa1d3](https://github.com/hyperi-io/vector-vrl/commit/44aa1d37653c2f1a62168bc0d908071a705c495c))

## [1.0.11](https://github.com/hyperi-io/vector-vrl/compare/v1.0.10...v1.0.11) (2026-10-23)

### Bug Fixes

* **security:** update rustls-webpki to 0.103.16 and certifi to 2026.10.19 ([#49](https://github.com/hyperi-io/vector-vrl/issues/49)) ([96cc9ae](https://github.com/hyperi-io/vector-vrl/commit/96cc9aeb3f6b57ff4e737643a72a4347b959ceb8))

## [1.0.10](https://github.com/hyperi-io/vector-vrl/compare/v1.0.9...v1.0.10) (2026-10-14)

### Bug Fixes

* bump pinned Vector version to 0.59.0-debian ([#45](https://github.com/hyperi-io/vector-vrl/issues/45)) ([8e2a1b3](https://github.com/hyperi-io/vector-vrl/commit/8e2a1b39dd831d9b77abcf6b1299f70301c45f59))
* repair the Vector auto-update workflow ([#43](https://github.com/hyperi-io/vector-vrl/issues/43)) ([744af29](https://github.com/hyperi-io/vector-vrl/commit/744af2962b976f9aac4ba4a83c68c7fb744e72c0))
* take rustls 0.23.46 and domain 0.12.3 ([#46](https://github.com/hyperi-io/vector-vrl/issues/46)) ([cb364ac](https://github.com/hyperi-io/vector-vrl/commit/cb364ac7052167a02d7ad22c1a343abe95c80d5b))

## [1.0.9](https://github.com/hyperi-io/vector-vrl/compare/v1.0.8...v1.0.9) (2026-10-14)

### Bug Fixes

* **ci:** install hyperi-ci on Python 3.14 so the release stage exists ([#40](https://github.com/hyperi-io/vector-vrl/issues/40)) ([ce5c65a](https://github.com/hyperi-io/vector-vrl/commit/ce5c65a12dc95e3c33221f1e022c531048576bca))

## [1.0.7](https://github.com/hyperi-io/vector-vrl/compare/v1.0.6...v1.0.7) (2026-09-01)

### Bug Fixes

* **ci:** give the publish step a gh token so it can cut the release ([5125dc2](https://github.com/hyperi-io/vector-vrl/commit/5125dc26b4b8ea21ca6765561ece393cce460375))
