Mining results workbook filenames are configured in SENAITE Setup → ID Server
→ Formatting Configuration, in the `ResultsReport` row.

The default format (without the automatically added `.xlsx` extension) is:

```
COA{year}-{seq:04d} {clientId} {yymmdd} {hh:mm}
```

For example: `COA26-0001 Plant 261008 09:15.xlsx`.

`{year}` and `{yymmdd}` retain the ID Server's two-digit year and compact date
formats. `{hh:mm}` supplies the current server time in 24-hour format, with
zero-padded hours and minutes. `{clientId}` is the client's configured ID.
Use sequence type `generated` and split length `1` to maintain a yearly counter
shared with all ResultsReport objects. Saving a workbook consumes only the
report's own sequence number; assigning its filename does not advance it again.

Existing ResultsReport formats are preserved. Set the row's format to the
example above to include client, date, and time. Installation and upgrades add
the default only when ResultsReport has no configuration, and remove the
obsolete MiningResultsXLSX row from the earlier implementation.

The filename is assigned when the report is saved and retained when its results
are refreshed. Email attachments, direct downloads, and files inside bulk ZIP
downloads use this saved name. Previously saved reports retain their filenames.
