# TODO

## Family Billing Follow-ups

- [ ] Добавить split / remove member flow: как безопасно выводить ученика из семьи с переносом его открытых долгов и кредитного баланса в новый individual account
- [ ] Сделать merge / consolidation flow для двух family accounts, если семью завели дублем
- [ ] Расширить M-Pesa matching: поддержать `billing_account_number` как основной BillRef и UI для ручной привязки платежа сразу к family account
- [ ] Добавить printable / PDF statement на уровне family billing account
- [ ] Продумать отдельный reversal flow для случаев, когда нужно перекинуть уже completed payment между family accounts

## Paid Activities Follow-ups

- [ ] Добавить refund / reversal flow для случая, когда участника нужно исключить после частичной или полной оплаты `activity` invoice
- [ ] Сделать отдельный отчёт/экспорт по collection rate и outstanding amount для activities
- [ ] Добавить bulk actions на detail page: массовое исключение и массовое добавление late participants
- [ ] Добавить reminder / communication flow по activity due date (например, список не оплативших)
- [ ] Решить, нужен ли отдельный printable roster / participant export CSV для активности
