# openai 3.42.0

## [3.42.0](https://github.com/openai/openai-python/compare/v3.41.0...v3.42.0) (2026-10-31)


### Features

* **api:** add agent context compaction settings ([#4209](https://github.com/openai/openai-python/issues/4209)) ([f552fcf](https://github.com/openai/openai-python/commit/f552fcffcf774520e946121704b5fbbf7ba986e8))
* **api:** add agent session review and tool settings ([#4217](https://github.com/openai/openai-python/issues/4217)) ([a63c4cd](https://github.com/openai/openai-python/commit/a63c4cdb1c758af3a2ca8edace3b5291f8b0318a))
* **api:** add experimental agent time awareness ([#4211](https://github.com/openai/openai-python/issues/4211)) ([10f9dd0](https://github.com/openai/openai-python/commit/10f9dd012363229a6c6f3fddb73403427fcd5eef))
* **api:** add image edit markup overlays ([#4210](https://github.com/openai/openai-python/issues/4210)) ([72c656d](https://github.com/openai/openai-python/commit/72c656df672989eed60c85bfafeb57f578fcc2ef))
* **api:** add organization external key management ([#4205](https://github.com/openai/openai-python/issues/4205)) ([3ee373e](https://github.com/openai/openai-python/commit/3ee373e038dd0756eba7d748605e5209bc5b726c))
* **api:** add SIP DTMF commands and delivery events ([#4208](https://github.com/openai/openai-python/issues/4208)) ([f9f3f76](https://github.com/openai/openai-python/commit/f9f3f76cf3af2c12675574a16804f3592a4f718a))
* **api:** improve WebSocket recovery and delivery reporting ([#4213](https://github.com/openai/openai-python/issues/4213)) ([68b962c](https://github.com/openai/openai-python/commit/68b962c7368c2c955771c731a769e5ef15e8f781))
* **api:** keep callable API keys scoped to each request ([#4216](https://github.com/openai/openai-python/issues/4216)) ([85bb536](https://github.com/openai/openai-python/commit/85bb536ad1ec5664d669544ca56b5e41701b1cdd))
* **api:** support response format updates and local output types ([#4212](https://github.com/openai/openai-python/issues/4212)) ([bd61e84](https://github.com/openai/openai-python/commit/bd61e84ca80c3579f1336a2d55c79bc5dca57a57))
* **api:** support WebSocket warmup and preserve cleanup cancellation ([#4215](https://github.com/openai/openai-python/issues/4215)) ([9abd656](https://github.com/openai/openai-python/commit/9abd656973e0c485419db159815de17d29c2b7a3))


### Bug Fixes

* preserve refusal output and authentication in WebSocket helpers ([#4214](https://github.com/openai/openai-python/issues/4214)) ([0599203](https://github.com/openai/openai-python/commit/05992039b9f7b78a48cf1e5a35727ba27d96db6e))