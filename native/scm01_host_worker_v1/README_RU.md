# SCM01 Host Worker V1 (HWA01)

Закрытый production-кандидат доверенного host-only worker.

- Default operator-facing entrypoint: CLOSED/92.
- Fixed profile: `HWA01_FIXED_SHA256_PROBE_V1`.
- Arbitrary Python/shell/model code is not an accepted operation.
- Source119/BEN01, Windows Sandbox and guest authority are separate and remain closed.
- The first Windows one-shot happy path was observed successfully before this landing candidate; that evidence does not itself authorize future execution.

`tests/` contains source/model/fake-port regression tests. One-shot launcher/evaluation tooling is intentionally not part of this production package.

Regression tests are host-portable: non-Windows refusal branches are tested by an explicit temporary platform fixture rather than by assuming the evaluator host is Linux.
