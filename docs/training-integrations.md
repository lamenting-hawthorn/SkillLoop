# SkillLoop Training Integrations Roadmap

Current stance: SkillLoop should autonomously prepare and judge training data from Hermes's existing execution substrate, but should not automatically run or promote fine-tunes until the controller, readiness, cost, evaluation, and approval gates are implemented.

Critical architecture rule: Hermes remains the live runtime and source of truth for sessions, tools, memory, skills, cron, gateway, and subagents. SkillLoop should govern learning artifacts derived from Hermes history; it should not rebuild a competing Hermes runtime.

## Intended autonomous flow

```text
Hermes state.db sessions/messages/tool calls
  -> SkillLoop controller tick
  -> eval + condition gates
  -> proposal queue
  -> SFT/DPO dataset refresh
  -> dataset readiness judge
  -> training plan proposal
  -> approval gate
  -> training runner
  -> candidate model evaluation
  -> promotion proposal
```

## What exists today

- SFT JSONL export.
- Conservative DPO export for explicit preference pairs.
- Train/validation/test split support.
- Dataset manifests with counts, estimated tokens, output files, provenance.
- Training config generation for Unsloth, TRL, and Axolotl.
- Explicit no-auto-training safety flags.

## What must exist before autonomous training

1. Dataset readiness judge.
   - Minimum record count.
   - Minimum estimated tokens.
   - Validation split required.
   - Average evaluation score threshold.
   - Low-score record cap.
   - Duplicate/near-duplicate checks.
   - Secret-like content scan.
   - Explicit recommendation: collect more data, ready to plan, or blocked.

2. Training plan object.
   - Target library: Unsloth, TRL, Axolotl.
   - Base model.
   - Dataset manifest.
   - Hyperparameters.
   - Expected output paths.
   - Cost/time/hardware estimates where available.
   - Approval requirement.

3. Training runner.
   - Manual/approved execution only at first.
   - Captures logs, exit status, checkpoint paths, runtime, cost placeholder.
   - Never stores hub tokens or credentials in SkillLoop state.

4. Candidate model registry.
   - Base model identity.
   - Adapter/checkpoint path.
   - Dataset manifest used.
   - Training config used.
   - Training run ID.
   - Provenance hashes.

5. Evaluation harness.
   - Compare candidate against baseline.
   - Use held-out validation traces and regression prompts.
   - Report improvements, regressions, safety failures.

6. Promotion policy.
   - No auto-promotion initially.
   - Promotion becomes a reviewed proposal.
   - Require minimum score improvement and no critical regression.

## Target install/deploy UX

Final user setup should be one or two commands max:

```bash
git clone <repo>
cd skillloop
./install.sh
```

or:

```bash
skillloop setup --connect hermes --start
```

Setup should:

- Install package/dependencies.
- Create local `.skillloop/` state.
- Detect/connect Hermes profile.
- Write default conservative policy.
- Install background runner using launchd/systemd/cron depending on OS.
- Start controller.
- Print status and next scheduled tick.

## Product rule

The normal user talks to Hermes, not SkillLoop. SkillLoop runs in the background and only surfaces approvals, summaries, and important warnings.
