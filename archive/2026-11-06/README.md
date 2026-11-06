# 2026-11-06 整书验证与入库代码档案

这是已执行试验的代码留档，保留验证过程中的单书假设。文件使用 `.py.txt`，不作为可直接运行的维护入口。当前可复用入口见 `tools/`。

只保存代码，不包含PDF、原文、知识页、模型回答、事件日志或凭证。本机用户目录已替换为 `<LOCAL_HOME>`。以下保留原代码校验值与去路径后的档案校验值，便于追溯。

| 文件 | 原代码 SHA256 | 档案 SHA256 |
|---|---|---|
| validation/audit-preview.py.txt | 192d5a73a7a2da45ab6b710949bb9d83b32a3c1caede970a78483da1648f06ab | ceb93c0463780cc8bee6bd366a8ff670fc21b550eec9111e9df9f8ca39a30f11 |
| validation/audit-queries.py.txt | 5bcf735559753d3fb7c8eea21524a7de2ea9462dede668def296408668ac1487 | 70137894471fc324a2f8309c8e1dec2cb1d0249d549570ca6347d1395ca6faa0 |
| validation/checkpoint.py.txt | a3e0c6075f4577b3a7b9938b49ba052d62aa340a974937870a0d457ddd984f95 | 5cce725d7066749aa1c0dc6ceeeffe8f37c064054627e319130c2624689641f8 |
| validation/finalize-deliverables.py.txt | 6daa41493b6d9f9c5af89804a0de3cb9503b82a893e0157f0f991f5ac6c634e3 | 2e84c2375aed34419b75775840f5c9d39e1accf14cb5e32093d88654953d6585 |
| validation/local-qwen-test.py.txt | 37c29c0c6de66873fadaeb3d66ac0cd39971ac10777e72302b81b7562e00b49b | 4764e04c2d23e27016b5842089b490e32dd52d95ff9e00fd45bc9c8de4a1a67f |
| validation/normalize-and-validate.py.txt | 70196e747d5d4d5f5b4d0c7466c0ca6c5e867616d20387989a213e5af61e6620 | 001aaab89be80f3671583b968da98699e31520c70b2a28d8b995a313267598b8 |
| import/import_book.py.txt | da71d00d053f55e85e53c06f5213e77d3983858628b99e74753b76388e2fe2e6 | c684098a29cae74f2ddeb7a7d75143a7ac964038587deb851221da26051174b0 |
| import/verify_import.py.txt | 0e2970d119f596dca3eb7156d15c6c5944d5d5b353a40b8be8331b10d441f407 | 402c352d2ec442677f8ce6cc0d942b4b5d24c4c57e5853cb0d9a240cd8bffdab |
