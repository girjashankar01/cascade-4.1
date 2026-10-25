# Stage 1 contrast measurements

Measured 2026-10-26 from frontend/src/design/tokens.css. Reproduce with npm run check:contrast. Text requires 4.5:1; focus/control boundaries require 3:1. Disabled text is included despite its contrast exemption.

| Theme | Foreground | Background | Ratio | Required | Result |
|---|---|---|---:|---:|---|
| light | text #17231d | canvas #f5f7f4 | 15.06:1 | 4.5:1 | PASS |
| light | muted #53635a | canvas #f5f7f4 | 5.91:1 | 4.5:1 | PASS |
| light | focus #8a5a18 | canvas #f5f7f4 | 5.48:1 | 3:1 | PASS |
| light | control-border #748278 | canvas #f5f7f4 | 3.74:1 | 3:1 | PASS |
| light | text #17231d | surface #ffffff | 16.22:1 | 4.5:1 | PASS |
| light | muted #53635a | surface #ffffff | 6.36:1 | 4.5:1 | PASS |
| light | focus #8a5a18 | surface #ffffff | 5.90:1 | 3:1 | PASS |
| light | control-border #748278 | surface #ffffff | 4.03:1 | 3:1 | PASS |
| light | text #17231d | recessed #e9eee8 | 13.80:1 | 4.5:1 | PASS |
| light | muted #53635a | recessed #e9eee8 | 5.41:1 | 4.5:1 | PASS |
| light | focus #8a5a18 | recessed #e9eee8 | 5.02:1 | 3:1 | PASS |
| light | control-border #748278 | recessed #e9eee8 | 3.43:1 | 3:1 | PASS |
| light | text #17231d | attention-surface #fbe9cc | 13.62:1 | 4.5:1 | PASS |
| light | muted #53635a | attention-surface #fbe9cc | 5.34:1 | 4.5:1 | PASS |
| light | focus #8a5a18 | attention-surface #fbe9cc | 4.96:1 | 3:1 | PASS |
| light | control-border #748278 | attention-surface #fbe9cc | 3.39:1 | 3:1 | PASS |
| light | action-ink #17231d | action #f2b35c | 8.79:1 | 4.5:1 | PASS |
| light | action-ink #17231d | action-hover #e9a74a | 7.79:1 | 4.5:1 | PASS |
| light | action-ink #17231d | action-active #e4a044 | 7.27:1 | 4.5:1 | PASS |
| light | allowed #22643c | allowed-surface #e1f0e6 | 6.02:1 | 4.5:1 | PASS |
| light | blocked #9b302e | blocked-surface #f9e9e7 | 6.25:1 | 4.5:1 | PASS |
| light | attention #6b420b | attention-surface #fbe9cc | 7.32:1 | 4.5:1 | PASS |
| light | selection-ink #17231d | selection #fbe9cc | 13.62:1 | 4.5:1 | PASS |
| dark | text #f5f7f4 | canvas #111b18 | 16.33:1 | 4.5:1 | PASS |
| dark | muted #b2beb6 | canvas #111b18 | 9.16:1 | 4.5:1 | PASS |
| dark | focus #f2b35c | canvas #111b18 | 9.53:1 | 3:1 | PASS |
| dark | control-border #81988b | canvas #111b18 | 5.69:1 | 3:1 | PASS |
| dark | text #f5f7f4 | surface #1b2723 | 14.32:1 | 4.5:1 | PASS |
| dark | muted #b2beb6 | surface #1b2723 | 8.03:1 | 4.5:1 | PASS |
| dark | focus #f2b35c | surface #1b2723 | 8.36:1 | 3:1 | PASS |
| dark | control-border #81988b | surface #1b2723 | 4.99:1 | 3:1 | PASS |
| dark | text #f5f7f4 | recessed #24332b | 12.31:1 | 4.5:1 | PASS |
| dark | muted #b2beb6 | recessed #24332b | 6.91:1 | 4.5:1 | PASS |
| dark | focus #f2b35c | recessed #24332b | 7.19:1 | 3:1 | PASS |
| dark | control-border #81988b | recessed #24332b | 4.29:1 | 3:1 | PASS |
| dark | text #f5f7f4 | attention-surface #3b2f1c | 12.11:1 | 4.5:1 | PASS |
| dark | muted #b2beb6 | attention-surface #3b2f1c | 6.79:1 | 4.5:1 | PASS |
| dark | focus #f2b35c | attention-surface #3b2f1c | 7.07:1 | 3:1 | PASS |
| dark | control-border #81988b | attention-surface #3b2f1c | 4.22:1 | 3:1 | PASS |
| dark | action-ink #17231d | action #f2b35c | 8.79:1 | 4.5:1 | PASS |
| dark | action-ink #17231d | action-hover #fac479 | 10.22:1 | 4.5:1 | PASS |
| dark | action-ink #17231d | action-active #e9a74a | 7.79:1 | 4.5:1 | PASS |
| dark | allowed #a6dfba | allowed-surface #153d29 | 8.02:1 | 4.5:1 | PASS |
| dark | blocked #ffc1bd | blocked-surface #4a2423 | 8.68:1 | 4.5:1 | PASS |
| dark | attention #f2b35c | attention-surface #3b2f1c | 7.07:1 | 4.5:1 | PASS |
| dark | selection-ink #17231d | selection #f2b35c | 8.79:1 | 4.5:1 | PASS |

46 pairs measured; 0 failures. No alpha text, artwork, or decorative dividers are treated as control boundaries.
