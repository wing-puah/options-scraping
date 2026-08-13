                         ANALYSIS ENGINE
                              │
                              ▼
                       795-row research book
                              │
             ┌────────────────┴─────────────────┐
             ▼                                  ▼
       SELECTION                            MANAGEMENT
             │                                  │
     ┌───────┼────────┐                 ┌───────┼─────────┐
     ▼       ▼        ▼                 ▼       ▼         ▼
  regime    ML     next-day           exit   giveback   underlying
   tests   tests    confirmation      tests    tests      tests
     │       │        │                 │
     └───────┴────────┴─────────────────┘
                     │
                     ▼
               SHIPPED LADDER
               top 3 / day
                tiers A/B
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
        CORE        BEAR       VOL
       LONGS       HEDGE      SLEEVE
          │          │          │
          │          │          └─ calendar candidate
          │          └─ hedge selection
          │
          └──────────────┬───────────────┘
                         ▼
                  ACCOUNT SIMULATION
                         │
                   $25k / risk caps
                         │
                         ▼
                  DEPLOYABLE SYSTEM