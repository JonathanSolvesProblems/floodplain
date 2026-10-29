# openai 3.41.0

## [3.41.0](https://github.com/openai/openai-python/compare/v3.40.0...v3.41.0) (2026-10-28)


### Features

* **api:** accept typed references in Realtime response inputs ([#4189](https://github.com/openai/openai-python/issues/4189)) ([8ecb487](https://github.com/openai/openai-python/commit/8ecb487ceb746f3af492c2d94083eb4e5d82a14f))
* **api:** add response tool usage models ([#4201](https://github.com/openai/openai-python/issues/4201)) ([55fc500](https://github.com/openai/openai-python/commit/55fc5008533deef3ad99ab6ffe48021e95aa22c2))
* **api:** filter agent sessions by metadata ([#4200](https://github.com/openai/openai-python/issues/4200)) ([77fd116](https://github.com/openai/openai-python/commit/77fd116d2326bc828bb23d4fd7960142972293a4))
* **websocket:** recover queued binary frames after reconnect ([#4191](https://github.com/openai/openai-python/issues/4191)) ([f079868](https://github.com/openai/openai-python/commit/f0798682d36be3bb79293d40c260cd93dbabf939))


### Bug Fixes

* **examples:** detect incomplete WebSocket responses ([#4187](https://github.com/openai/openai-python/issues/4187)) ([8559299](https://github.com/openai/openai-python/commit/8559299f866af4931293e9392f2829a20c545c0b))
* **examples:** handle interruptions and disconnects in push-to-talk ([#4192](https://github.com/openai/openai-python/issues/4192)) ([35fc9f3](https://github.com/openai/openai-python/commit/35fc9f33a769858475f2f512112c4256480fff41))
* keep consumer fixtures clean under strict Pyright ([#4204](https://github.com/openai/openai-python/issues/4204)) ([5012565](https://github.com/openai/openai-python/commit/501256573272e172fb5a39ecf36ca0c27f1ea40d))


### Chores

* **api:** document upcoming model shutdowns ([#4199](https://github.com/openai/openai-python/issues/4199)) ([5b43cce](https://github.com/openai/openai-python/commit/5b43cceea4a25bc1b9ed1b08f087408b47981083))
* **api:** update image-model documentation ([#4198](https://github.com/openai/openai-python/issues/4198)) ([fa67521](https://github.com/openai/openai-python/commit/fa67521e1c59f11fb5cba7ef8b9b35b5fcac2ae4))
* enforce generated-file ownership ([#4193](https://github.com/openai/openai-python/issues/4193)) ([1b37b9a](https://github.com/openai/openai-python/commit/1b37b9a85e857a7ada4db661bf867bf680290ccf))
* migrate development type checking to ty ([#4202](https://github.com/openai/openai-python/issues/4202)) ([45b9531](https://github.com/openai/openai-python/commit/45b9531d549df9b7c4af267d66ac5a5999bd9d31))