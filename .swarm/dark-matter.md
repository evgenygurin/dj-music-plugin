## Dark Matter: Hidden Couplings

Found 20 file pairs that frequently co-change but have no import relationship:

| File A | File B | NPMI | Co-Changes | Lift |
|--------|--------|------|------------|------|
| app/audio/deep/demucs_mlx_runner.py | app/config/stems.py | 1.000 | 5 | 100.00 |
| app/domain/transition/dj_mixing.py | app/tools/ui/mix_composer.py | 1.000 | 3 | 166.67 |
| app/domain/transition/dj_mixing.py | tests/domain/transition/test_dj_mixing.py | 1.000 | 3 | 166.67 |
| app/domain/transition/dj_mixing.py | tests/tools/ui/test_mix_composer_align.py | 1.000 | 3 | 166.67 |
| app/tools/multi_deck/compatibility.py | app/tools/multi_deck/energy_budget.py | 1.000 | 3 | 166.67 |
| app/tools/multi_deck/compatibility.py | app/tools/multi_deck/timeline.py | 1.000 | 3 | 166.67 |
| app/tools/multi_deck/energy_budget.py | app/tools/multi_deck/timeline.py | 1.000 | 3 | 166.67 |
| app/tools/ui/camelot_wheel.py | app/tools/ui/library_dashboard.py | 1.000 | 6 | 83.33 |
| app/tools/ui/mix_composer.py | tests/domain/transition/test_dj_mixing.py | 1.000 | 3 | 166.67 |
| app/tools/ui/mix_composer.py | tests/tools/ui/test_mix_composer_align.py | 1.000 | 3 | 166.67 |
| tests/domain/transition/test_dj_mixing.py | tests/tools/ui/test_mix_composer_align.py | 1.000 | 3 | 166.67 |
| .opencode/plugins/superpowers.js | .opencode/tui.json | 1.000 | 3 | 166.67 |
| app/audio/deep/beatgrid_builder.py | app/audio/deep/stem_analyzer.py | 1.000 | 3 | 166.67 |
| app/audio/deep/beatgrid_builder.py | app/handlers/deep_analysis.py | 1.000 | 3 | 166.67 |
| app/audio/deep/beatgrid_builder.py | tests/audio/deep/test_stem_analyzer.py | 1.000 | 3 | 166.67 |
| app/audio/deep/stem_analyzer.py | app/handlers/deep_analysis.py | 1.000 | 3 | 166.67 |
| app/audio/deep/stem_analyzer.py | tests/audio/deep/test_stem_analyzer.py | 1.000 | 3 | 166.67 |
| app/handlers/deep_analysis.py | tests/audio/deep/test_stem_analyzer.py | 1.000 | 3 | 166.67 |
| app/domain/render/request.py | app/domain/render/stem_voicing.py | 1.000 | 4 | 125.00 |
| app/domain/render/bar_plan.py | app/domain/render/plan_assembler.py | 1.000 | 3 | 166.67 |

These pairs likely share an architectural concern invisible to static analysis.
Consider adding explicit documentation or extracting the shared concern.