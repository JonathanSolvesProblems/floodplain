# openai 3.59.0

## [3.59.0](https://github.com/openai/openai-python/compare/v3.58.0...v3.59.0) (2026-11-24)


### Features

* **api:** add healthcare model IDs for Responses ([#4327](https://github.com/openai/openai-python/issues/4327)) ([804a9af](https://github.com/openai/openai-python/commit/804a9af5a5199f36d28dfdf84c7981f0253a3a3f))


### Bug Fixes

* check the agent upload directory after path resolution ([#4323](https://github.com/openai/openai-python/issues/4323)) ([bc02da4](https://github.com/openai/openai-python/commit/bc02da46f35fb2a85108dd41d4c49987cc5cb0fc))
* redact credential headers on API error requests ([#4316](https://github.com/openai/openai-python/issues/4316)) ([9d7f58e](https://github.com/openai/openai-python/commit/9d7f58e0a56eb2bf04984357d80f7409c0cf11eb))
* reject empty webhook signing keys ([#4321](https://github.com/openai/openai-python/issues/4321)) ([dd69803](https://github.com/openai/openai-python/commit/dd6980331425d76fe112a09b05eeb69588b0d841))
* reject non-finite numbers in agent tool arguments ([#4326](https://github.com/openai/openai-python/issues/4326)) ([abbd379](https://github.com/openai/openai-python/commit/abbd37925aa749ec35cd45cd94722e449f909388))
* use bearer authentication for beta Realtime sessions ([#4317](https://github.com/openai/openai-python/issues/4317)) ([7596fb8](https://github.com/openai/openai-python/commit/7596fb8b75bd5b95dbc618d148fb8b0f96ca2aea))


### Documentation

* explain how to skip duplicate webhook events ([#4325](https://github.com/openai/openai-python/issues/4325)) ([6805f05](https://github.com/openai/openai-python/commit/6805f051c31fde320df3d678d294c7aee7a97bc6))