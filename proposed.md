                     Main Claude
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
    Research Agent A          Research Agent B
    "Find patterns"            "Find patterns"
          │                         │
          └────────────┬────────────┘
                       ▼
                 Validator Agent
                       │
                       ▼
                 Main Claude
                       │
                 OOS decision

The important distinction is that A and B should independently analyse the data before either sees the other's conclusions.