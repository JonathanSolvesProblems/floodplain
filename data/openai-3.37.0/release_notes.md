# openai 3.37.0

## [3.37.0](https://github.com/openai/openai-python/compare/v3.36.1...v3.37.0) (2026-10-22)


### ⚠ BREAKING CHANGES

* **api:** This minor release includes a breaking change to Decisions types. In Live response models, question `instructions` can now be a string or a list of structured text, image, or JSON parts; check `isinstance(question.instructions, str)` before using string operations and handle the structured form. Decisions request input types also include additional message roles and tool-history items, so update exhaustive type checks accordingly. Existing string instructions and `DecisionInputMessageParam` user-message inputs remain supported.


### Features

* **api:** expand Decisions input and question types ([#4158](https://github.com/openai/openai-python/issues/4158)) ([1e45ad1](https://github.com/openai/openai-python/commit/1e45ad180ba409e3c31897710aa2a40129d58994))


### Chores

* **api:** preserve file and video polling helpers ([#4155](https://github.com/openai/openai-python/issues/4155)) ([7db9d88](https://github.com/openai/openai-python/commit/7db9d884c33b0d5ef252e9a4b6e7ae0bbd217e5b))
* **api:** preserve upload helpers and Live connection defaults ([#4152](https://github.com/openai/openai-python/issues/4152)) ([a29dc39](https://github.com/openai/openai-python/commit/a29dc3947aeccecc2e85d8fbad4d7c03b8af13e9))
* **deps:** bump astral-sh/setup-uv from 10.2.0 to 10.3.0 ([#4109](https://github.com/openai/openai-python/issues/4109)) ([fa9a161](https://github.com/openai/openai-python/commit/fa9a1616fd175e68dec9960d33dee2caefc0e8d3))