# Worked dialogues and fresh retrieval

Executed fixture interviews with the final installed wheel. Exact approval is
the simulated fixture-user approval of the actual prepared plan. This controlled
profile is distinct from live-model behavior. Raw data is retained in `trial/`.

## retry

Initial question: Please provide the CR link and the pull request link that implements it.

Source revisions: `{"base": "c383a199203f1eebc74398410f8613adc7ba12b4", "head": "3606f3e0a78522a513d0446d95d64495a529bb8e", "target": {"branch": "master", "commit": "3606f3e0a78522a513d0446d95d64495a529bb8e"}}`.

Agent: Retry.cs@3606f3e0a78522a513d0446d95d64495a529bb8e#L1-L1: Prefer four total transient operation attempts What explains choosing or preserving this approach, and when does that reason apply? This matters to preserve: Bound work within the caller deadline. Unknown/skip is acceptable.

Fixture user: max_attempts=4 fits the bounded transient operation budget.

Agent: Transport.cs@3606f3e0a78522a513d0446d95d64495a529bb8e#L1-L1: Leave the independent packet recovery in Transport unchanged What explains choosing or preserving this approach, and when does that reason apply? This matters to preserve: Do not multiply operation retries by changing packet recovery ownership. Unknown/skip is acceptable.

Fixture user: packet_attempts=2 is an independent per-packet recovery responsibility; changing it would multiply operation work.

Agent: Caller.cs@3606f3e0a78522a513d0446d95d64495a529bb8e#L1-L1: Preserve the caller deadline of 120 ms What explains choosing or preserving this approach, and when does that reason apply? This matters to preserve: Do not extend the public caller deadline. Unknown/skip is acceptable.

Fixture user: caller_deadline_ms=120 is the existing public caller budget.

The concrete plan was prepared, approved, applied and acknowledged. Saved records:

* `ucr.5917a2eacdf368ff.retry-limit` revision 1; CONFIRMED
* `ucr.5917a2eacdf368ff.transport-owner` revision 1; CONFIRMED
* `ucr.5917a2eacdf368ff.deadline` revision 1; CONFIRMED

Fresh process input: An equivalent transient operation: bounded retry, independent transport recovery, caller deadline

Normal context returned 3 applicable claims. Recovered plan:

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

Separate oracle: PASS. Actual .NET output:

```text
PASS retry behavioral oracle; caller and packet owner unchanged
```

## cache

Initial question: Пришлите ссылку на CR и ссылку на pull request, который его реализует.

Source revisions: `{"base": "929de779f59be68fece4670407c6a482e962431d", "head": "833b7b00ef54db507a3f495c5db41252112d9dc7", "target": {"branch": "master", "commit": "833b7b00ef54db507a3f495c5db41252112d9dc7"}}`.

Agent: Cache.cs@833b7b00ef54db507a3f495c5db41252112d9dc7#L1-L1: Для справочника использовать ограниченный кэш ёмкостью 32 записи Почему выбран или сохранён этот вариант? Укажите причину и условия применимости; это важно для сохранения ограничения: Ограничение памяти и прежнее поведение при промахе. Неизвестно/пропустить — допустимый ответ.

Fixture user: cache_capacity=32 ограничивает расход памяти; сохранить поведение при промахе.

Agent: Contracts.cs@833b7b00ef54db507a3f495c5db41252112d9dc7#L1-L1: Публичный интерфейс ILookup.Find оставить прежним Почему выбран или сохранён этот вариант? Укажите причину и условия применимости; это важно для сохранения ограничения: Не менять сигнатуру Find и совместимость потребителей. Неизвестно/пропустить — допустимый ответ.

Fixture user: Нужна совместимость прежних потребителей ILookup; сохранить сигнатуру Find.

The concrete plan was prepared, approved, applied and acknowledged. Saved records:

* `ucr.7ba1e88c78b8d81b.capacity` revision 1; CONFIRMED
* `ucr.7ba1e88c78b8d81b.contract` revision 1; CONFIRMED

Fresh process input: Эквивалентный справочник: кэш память интерфейс ILookup Find и поведение при промахе

Normal context returned 2 applicable claims. Recovered plan:

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

Separate oracle: PASS. Actual .NET output:

```text
PASS cache behavioral oracle; ILookup.Find unchanged
```
