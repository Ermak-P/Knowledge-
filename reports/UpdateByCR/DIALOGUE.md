# Worked dialogues and fresh retrieval

These are executed fixture interviews using the final installed wheel. Approval
is the explicitly simulated fixture-user approval of the actual prepared plan.
They are controlled profiles, not live-model conversations. Raw source, questions,
answers, canonical receipts and fresh context are in `trial/`.

## retry

Initial question: Please provide the CR link and the pull request link that implements it.

Source revisions: `{"base": "6cbde48c94c9b3731cb452a4e8ec28c9e9508d9c", "head": "98766373c7a424d0e51331ca4ba96053b8e8c436", "target": {"branch": "master", "commit": "98766373c7a424d0e51331ca4ba96053b8e8c436"}}`.

Agent: Retry.cs@98766373c7a424d0e51331ca4ba96053b8e8c436#L1-L1: Prefer four total transient operation attempts What explains choosing or preserving this approach, and when does that reason apply? This matters to preserve: Bound work within the caller deadline. Unknown/skip is acceptable.

Fixture user: max_attempts=4 fits the bounded transient operation budget.

Agent: Transport.cs@98766373c7a424d0e51331ca4ba96053b8e8c436#L1-L1: Leave the independent packet recovery in Transport unchanged What explains choosing or preserving this approach, and when does that reason apply? This matters to preserve: Do not multiply operation retries by changing packet recovery ownership. Unknown/skip is acceptable.

Fixture user: packet_attempts=2 is an independent per-packet recovery responsibility; changing it would multiply operation work.

Agent: Caller.cs@98766373c7a424d0e51331ca4ba96053b8e8c436#L1-L1: Preserve the caller deadline of 120 ms What explains choosing or preserving this approach, and when does that reason apply? This matters to preserve: Do not extend the public caller deadline. Unknown/skip is acceptable.

Fixture user: caller_deadline_ms=120 is the existing public caller budget.

The concrete plan was prepared, approved, applied and acknowledged. Saved records:

* `ucr.e4a7e408bd78bf29.retry-limit` revision 1; CONFIRMED
* `ucr.e4a7e408bd78bf29.transport-owner` revision 1; CONFIRMED
* `ucr.e4a7e408bd78bf29.deadline` revision 1; CONFIRMED

Fresh process input: An equivalent transient operation: bounded retry, independent transport recovery, caller deadline

The normal context interface returned 3 applicable claims. The controlled planner recovered:

```json
{
  "parameters": {
    "packet_attempts": 2,
    "max_attempts": 4,
    "caller_deadline_ms": 120
  },
  "preserve": [
    "Do not multiply operation retries by changing packet recovery ownership",
    "Bound work within the caller deadline",
    "Do not extend the public caller deadline"
  ],
  "reasons": [
    "packet_attempts=2 is an independent per-packet recovery responsibility; changing it would multiply operation work",
    "max_attempts=4 fits the bounded transient operation budget",
    "caller_deadline_ms=120 is the existing public caller budget"
  ]
}
```

Separate oracle: PASS. Actual .NET behavior output:

```text
PASS retry behavioral oracle; caller and packet owner unchanged
```

## cache

Initial question: Пришлите ссылку на CR и ссылку на pull request, который его реализует.

Source revisions: `{"base": "5249929a4753e86f3a65f383f1309321c8eb1c41", "head": "fe524cd429ed3f8ab8b23e01256600d7dd859b09", "target": {"branch": "master", "commit": "fe524cd429ed3f8ab8b23e01256600d7dd859b09"}}`.

Agent: Cache.cs@fe524cd429ed3f8ab8b23e01256600d7dd859b09#L1-L1: Для справочника использовать ограниченный кэш ёмкостью 32 записи Почему выбран или сохранён этот вариант? Укажите причину и условия применимости; это важно для сохранения ограничения: Ограничение памяти и прежнее поведение при промахе. Неизвестно/пропустить — допустимый ответ.

Fixture user: cache_capacity=32 ограничивает расход памяти; сохранить поведение при промахе.

Agent: Contracts.cs@fe524cd429ed3f8ab8b23e01256600d7dd859b09#L1-L1: Публичный интерфейс ILookup.Find оставить прежним Почему выбран или сохранён этот вариант? Укажите причину и условия применимости; это важно для сохранения ограничения: Не менять сигнатуру Find и совместимость потребителей. Неизвестно/пропустить — допустимый ответ.

Fixture user: Нужна совместимость прежних потребителей ILookup; сохранить сигнатуру Find.

The concrete plan was prepared, approved, applied and acknowledged. Saved records:

* `ucr.e8c7d3a93d2e9aed.capacity` revision 1; CONFIRMED
* `ucr.e8c7d3a93d2e9aed.contract` revision 1; CONFIRMED

Fresh process input: Эквивалентный справочник: кэш память интерфейс ILookup Find и поведение при промахе

The normal context interface returned 2 applicable claims. The controlled planner recovered:

```json
{
  "parameters": {
    "cache_capacity": 32
  },
  "preserve": [
    "Не менять сигнатуру Find и совместимость потребителей",
    "Ограничение памяти и прежнее поведение при промахе"
  ],
  "reasons": [
    "Нужна совместимость прежних потребителей ILookup; сохранить сигнатуру Find",
    "cache_capacity=32 ограничивает расход памяти; сохранить поведение при промахе"
  ]
}
```

Separate oracle: PASS. Actual .NET behavior output:

```text
PASS cache behavioral oracle; ILookup.Find unchanged
```
