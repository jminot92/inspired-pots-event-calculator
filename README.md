# Inspired Pots Event Calculator

The first version is deliberately small: enter an event price, see potential staff commission and check the minimum to charge. Saving/reopening is hidden until durable storage is available.

## Open it

From this folder run `run.ps1`, then open **http://127.0.0.1:8501**.

```powershell
Set-Location 'C:\Users\jackm\Documents\Inspired Pots\inspired_pots_quote_app'
.\run.ps1
```

The launcher uses the local Codex Python/dependencies on this computer. For another computer with Python 3.12+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Use it

1. Use the navigation bar to choose remote event, private studio hire or pottery selection.
2. Set painters and pottery package; indicative pottery values are displayed. For remote events, enter a destination and open directions from Inspired Pots in Google Maps. Enter one-way miles and estimated minutes; the calculator doubles them for return travel. This link requires no API key.
3. Enter the proposed price per painter **ex VAT**, or a total studio hire fee for fee-only private bookings. The main price control sits above the results in a contrasting panel.
4. Review customer charge, potential staff commission and minimum to charge, in that order.

The prominent **Staff-generated enquiry** switch defaults OFF for inbound enquiries, with no staff commission. Turn it ON for staff-generated enquiries to apply the existing surplus commission. It never changes the protected minimum. **Pricing health** measures headroom retained after commission as a percentage of the ex-VAT charge: negative = Below minimum; under 5% = Close to break-even; 5–15% = Low price; 15–25% = Good pricing; 25% or more = Strong pricing. These are working guidance thresholds, not accounting profit or a compulsory price: pottery is protected at retail value and overheads are not separately modelled.

The **Check pricing assumptions** expander lets you review pottery value, consumables and staffing for the current calculation. These adjustments do not change global defaults.

**Pottery selection** has three package sections with checkboxes and editable prices (ex VAT). The highest selected price becomes the package pottery value, even if it is below the old configured safeguard. With no selections, the indicative retail defaults remain £15 / £18 / £25 inc VAT, displayed as £12.50 / £15 / £20.83 ex VAT. Original retail amounts are preserved when rounded display values are not edited. Choices and corrected prices carry across the navigation views for this session; they are not saved permanently. The bundled catalogue snapshot was loaded from Shopify on 2 October 2026 and is indicative. It contains 286 variants from active pottery products; fees, refreshments, gift cards, glazes and postage are excluded.

Shopify is **indicative**, not a verified price list. The default protects the higher of the configured package safeguard and assigned catalogue prices. A reviewed pottery amount can be set explicitly. Verify pottery and return travel before using the estimate. The API lookup service is preserved for the advanced interface.

All commercial calculations use Decimal and ex-VAT values. Remote commission only comes from revenue above the protected minimum. Simple private hire defaults to one staff member, four hours at £17/hour and £5 inc VAT consumables per painter. Package pricing protects pottery, consumables and staff; event-fee pricing protects consumables and staff while pottery is paid separately. Private commission is 50% of the ex-VAT surplus. The £250 inc VAT pottery sales target applies only when customers choose and pay for pottery on the day; it is shown as guidance in fee-only hire. Fixed packages are assessed on costs and surplus, with no £250 pottery warning. Fee-only hire uses a total studio hire charge; package selection and pottery spend forecasts are hidden in this mode. Both event types default to one staff member, adjustable in pricing assumptions. For 15 painters the fee floor is £130.50 ex VAT / £156.60 inc VAT. Legacy fixed/tiered private commission functions remain available to the deferred advanced workflow.

## Deferred features are preserved

Save/reopen, PDF/email exports, the full quote editor, saved-quote booking statuses, deposits, commission reporting, catalogue administration and settings/accounts remain in the codebase. They are **outside the current interface**. Nothing has been deleted. The simple calculator's preserved save functions use their own `calculations` table, separate from the fuller quote workflow; the current local SQLite file is not a durable hosted saving solution.

To bring back the full interface later, set `APP_MODE=advanced` before starting Streamlit. Its setup/reference documentation is retained in [docs/advanced.md](docs/advanced.md).

The app defaults to trusted local administrator access and binds only to loopback. Before exposing it to other computers, enable password authentication as described in the advanced documentation. SQLite data lives in `data/quotes.sqlite3`.

## Verification

Run `python -m pytest -q` from this folder after installing requirements. Tests cover Decimal pricing, the supplied £516.83 minimum / £21.59 commission example, saved-calculation reopening, ownership and version checks, plus the preserved advanced functions. Integration tests use mocked responses; live Shopify and Maps require credentials.


