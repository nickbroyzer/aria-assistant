"""HTML generators for invoice previews and paystubs."""

from datetime import datetime
from utils.config import load_config
from utils.constants import DEFAULT_SETTINGS


def _invoice_html(inv):
    items_html = ""
    for item in inv.get("line_items", []):
        qty = item.get("qty", 1)
        rate = float(item.get("rate", 0))
        amount = float(item.get("amount", 0))
        items_html += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;">{item.get('description','')}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:center;">{qty}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;">${rate:,.2f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;">${amount:,.2f}</td>
        </tr>"""

    tax_row = ""
    if inv.get("apply_tax") and inv.get("tax", 0) > 0:
        tax_row = f'<tr><td colspan="3" style="padding:6px 12px;text-align:right;color:#666;">WA Sales Tax ({inv["tax_rate"]*100:.1f}%)</td><td style="padding:6px 12px;text-align:right;">${inv["tax"]:,.2f}</td></tr>'

    status_color = {"draft":"#888","sent":"#2563eb","paid":"#16a34a","overdue":"#dc2626"}.get(inv.get("status","draft"),"#888")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Invoice {inv.get('invoice_number')}</title>
<style>
  body{{font-family:Arial,sans-serif;color:#222;margin:0;padding:0;background:#f5f5f5;}}
  .page{{max-width:760px;margin:32px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 20px rgba(0,0,0,0.1);}}
  @media print{{body{{background:#fff;}}.page{{margin:0;box-shadow:none;border-radius:0;}} .no-print{{display:none;}}}}
</style>
</head><body>
<div class="page">
  <div style="background:#1a1a1a;padding:28px 36px;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="font-size:22px;font-weight:800;color:#fff;letter-spacing:2px;">PACIFIC CONSTRUCTION</div>
      <div style="font-size:11px;color:#e8650a;letter-spacing:1.5px;margin-top:3px;">WAREHOUSE INSTALLATION SPECIALISTS</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:28px;font-weight:700;color:#e8650a;">INVOICE</div>
      <div style="color:#aaa;font-size:13px;margin-top:2px;">#{inv.get('invoice_number')}</div>
      <div style="display:inline-block;margin-top:6px;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;color:#fff;background:{status_color};">{inv.get('status','draft').upper()}</div>
    </div>
  </div>
  <div style="padding:28px 36px;">
    <div style="display:flex;justify-content:space-between;margin-bottom:28px;">
      <div>
        <div style="font-size:10px;font-weight:700;color:#999;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Bill To</div>
        <div style="font-weight:700;font-size:15px;">{inv.get('client_name','')}</div>
        <div style="color:#555;">{inv.get('client_company','')}</div>
        <div style="color:#555;white-space:pre-line;">{inv.get('client_address','')}</div>
        <div style="color:#555;">{inv.get('client_email','')}</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:10px;font-weight:700;color:#999;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">From</div>
        <div style="font-weight:700;">Pacific Construction</div>
        <div style="color:#555;">1574 Thornton Ave SW</div>
        <div style="color:#555;">Pacific, WA 98047</div>
        <div style="color:#555;">253.826.2727</div>
        <div style="margin-top:12px;">
          <div style="font-size:11px;color:#999;">Invoice Date: <strong>{inv.get('date','')}</strong></div>
          <div style="font-size:11px;color:#999;">Due Date: <strong>{inv.get('due_date','')}</strong></div>
        </div>
      </div>
    </div>
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
      <thead>
        <tr style="background:#f8f8f8;">
          <th style="padding:10px 12px;text-align:left;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Description</th>
          <th style="padding:10px 12px;text-align:center;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Qty</th>
          <th style="padding:10px 12px;text-align:right;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Rate</th>
          <th style="padding:10px 12px;text-align:right;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Amount</th>
        </tr>
      </thead>
      <tbody>{items_html}</tbody>
      <tfoot>
        <tr><td colspan="3" style="padding:8px 12px;text-align:right;font-weight:600;">Subtotal</td><td style="padding:8px 12px;text-align:right;">${inv.get('subtotal',0):,.2f}</td></tr>
        {tax_row}
        <tr style="background:#1a1a1a;"><td colspan="3" style="padding:12px;text-align:right;font-weight:700;color:#fff;font-size:15px;">TOTAL</td><td style="padding:12px;text-align:right;font-weight:700;color:#e8650a;font-size:18px;">${inv.get('total',0):,.2f}</td></tr>
      </tfoot>
    </table>
    {f'<div style="background:#f9f9f9;border-radius:6px;padding:14px;font-size:13px;color:#555;margin-bottom:16px;"><strong>Notes:</strong> {inv.get("notes","")}</div>' if inv.get("notes") else ""}
    <div style="border-top:2px solid #e8650a;padding-top:14px;text-align:center;font-size:11px;color:#999;">
      Pacific Construction · 1574 Thornton Ave SW, Pacific, WA 98047 · 253.826.2727
    </div>
  </div>
</div>
<div class="no-print" style="text-align:center;padding:16px;">
  <button onclick="window.print()" style="background:#e8650a;color:#fff;border:none;padding:10px 24px;border-radius:6px;font-size:14px;font-weight:700;cursor:pointer;">Print / Save as PDF</button>
</div>
</body></html>"""


def _paystub_html(record, person, ytd_gross, ytd_paid):
    from markupsafe import escape as e
    co_cfg = load_config().get("company", DEFAULT_SETTINGS["company"])
    co_name = co_cfg.get("name", "Pacific Construction")
    co_addr = f"{co_cfg.get('address','')}, {co_cfg.get('city','')}, {co_cfg.get('state','')} {co_cfg.get('zip','')}"
    co_phone = co_cfg.get("phone", "")

    is_employee = person.get("qb_type") == "employee"
    gross       = float(record.get("amount_paid") or 0)
    amount_due  = float(record.get("amount_due")  or 0)
    pay_date      = record.get("pay_date", "—")
    period_start  = record.get("period_start", "")
    period_end    = record.get("period_end", "")
    description   = record.get("description", "—")
    job_num       = record.get("job_number", "")
    stub_num      = record.get("pay_id", "")[:8].upper()

    # Format dates nicely
    try:
        from datetime import datetime as dt
        pay_date_fmt = dt.strptime(pay_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        pay_date_fmt = pay_date

    try:
        period_fmt = (dt.strptime(period_start, "%Y-%m-%d").strftime("%b %d, %Y")
                      + " – " + dt.strptime(period_end, "%Y-%m-%d").strftime("%b %d, %Y"))
    except Exception:
        period_fmt = ""

    # Pay type display
    pay_type_map  = {"hourly":"Hourly","salary":"Salary","per_job":"Per Job","contract":"Contract"}
    terms_map     = {"immediate":"Due on Receipt","net15":"Net 15","net30":"Net 30",
                     "weekly":"Weekly","biweekly":"Bi-Weekly","monthly":"Monthly"}
    pay_type_str  = pay_type_map.get(person.get("pay_type",""), person.get("pay_type",""))
    pay_rate      = float(person.get("pay_rate") or 0)
    pay_terms_str = terms_map.get(person.get("pay_terms",""), person.get("pay_terms",""))

    # WA state: no state income tax
    fed_rate  = 0.22
    ss_rate   = 0.062
    med_rate  = 0.0145

    if is_employee:
        fed_tax  = round(gross * fed_rate, 2)
        ss_tax   = round(gross * ss_rate,  2)
        med_tax  = round(gross * med_rate, 2)
        total_ded = round(fed_tax + ss_tax + med_tax, 2)
        net_pay   = round(gross - total_ded, 2)

        ytd_fed   = round(ytd_paid * fed_rate, 2)
        ytd_ss    = round(ytd_paid * ss_rate,  2)
        ytd_med   = round(ytd_paid * med_rate, 2)
        ytd_net   = round(ytd_paid - ytd_fed - ytd_ss - ytd_med, 2)

        rate_line = ""
        if pay_rate and pay_type_str == "Hourly":
            rate_line = f"<div class='info-row'><span class='lbl'>Pay Rate</span><span>${pay_rate:,.2f} / hr</span></div>"
        elif pay_rate and pay_type_str == "Salary":
            rate_line = f"<div class='info-row'><span class='lbl'>Annual Salary</span><span>${pay_rate:,.0f}</span></div>"

        pay_terms_raw = person.get("pay_terms", "")
        if pay_terms_raw == "weekly":
            period_label = "Weekly Pay"
            divisor_note = f" (${pay_rate:,.0f}/yr ÷ 52)" if pay_rate and pay_type_str == "Salary" else ""
        else:
            period_label = "Bi-Weekly Pay"
            divisor_note = f" (${pay_rate:,.0f}/yr ÷ 26)" if pay_rate and pay_type_str == "Salary" else ""

        earn_label = f"{period_label} — {period_fmt}" if period_fmt else e(description)
        if pay_rate and pay_type_str == "Hourly":
            hrs = 40 if pay_terms_raw == "weekly" else 80
            earn_detail = f" ({hrs} hrs @ ${pay_rate:,.2f}/hr)"
        elif pay_rate and pay_type_str == "Salary":
            earn_detail = divisor_note
        else:
            earn_detail = ""

        earnings_block = f"""
        <div class='section-head'>Earnings</div>
        <table class='amt-table'>
          <tr><th>Description</th><th>Current</th><th>YTD</th></tr>
          <tr><td>{earn_label}{earn_detail}</td><td>${gross:,.2f}</td><td>${ytd_gross:,.2f}</td></tr>
        </table>

        <div class='section-head'>Deductions</div>
        <table class='amt-table'>
          <tr><th>Description</th><th>Current</th><th>YTD</th></tr>
          <tr><td>Federal Income Tax (est. {int(fed_rate*100)}%)</td><td>${fed_tax:,.2f}</td><td>${ytd_fed:,.2f}</td></tr>
          <tr><td>WA State Income Tax</td><td>$0.00</td><td>$0.00</td></tr>
          <tr><td>Social Security (6.2%)</td><td>${ss_tax:,.2f}</td><td>${ytd_ss:,.2f}</td></tr>
          <tr><td>Medicare (1.45%)</td><td>${med_tax:,.2f}</td><td>${ytd_med:,.2f}</td></tr>
          <tr class='subtotal'><td><strong>Total Deductions</strong></td><td><strong>${total_ded:,.2f}</strong></td><td><strong>${ytd_fed+ytd_ss+ytd_med:,.2f}</strong></td></tr>
        </table>

        <div class='net-pay-bar'>
          <div>
            <div class='net-label'>NET PAY</div>
            <div class='net-amount'>${net_pay:,.2f}</div>
          </div>
          <div class='net-ytd'>
            <div class='net-label'>YTD NET PAY</div>
            <div class='net-ytd-amt'>${ytd_net:,.2f}</div>
          </div>
        </div>

        <div class='notice'>
          <strong>Note:</strong> Tax amounts shown are estimates for record-keeping purposes.
          Actual withholding is calculated by payroll software at time of payment.
          Washington State has no state income tax. W-2 issued annually.
        </div>
        """

        left_col = f"""
          <div class='card-label'>Employee</div>
          <div class='card-name'>{e(person.get('name','—'))}</div>
          <div class='card-sub'>{e(person.get('role',''))}</div>
          <div class='info-block'>
            <div class='info-row'><span class='lbl'>Pay Type</span><span>{pay_type_str}</span></div>
            {rate_line}
            <div class='info-row'><span class='lbl'>Pay Frequency</span><span>{pay_terms_str}</span></div>
            {f"<div class='info-row'><span class='lbl'>Pay Period</span><span>{period_fmt}</span></div>" if period_fmt else ''}
            <div class='info-row'><span class='lbl'>QB Type</span><span>W-2 Employee</span></div>
            {f"<div class='info-row'><span class='lbl'>Tax ID</span><span>***{e(person.get('tax_id',''))}</span></div>" if person.get('tax_id') else ''}
          </div>
        """

    else:  # subcontractor — remittance advice
        balance = round(amount_due - gross, 2)

        earnings_block = f"""
        <div class='section-head'>Payment Detail</div>
        <table class='amt-table'>
          <tr><th>Description</th><th>Invoice Amount</th><th>Payment</th><th>Balance</th></tr>
          <tr>
            <td>{e(description)}</td>
            <td>${amount_due:,.2f}</td>
            <td>${gross:,.2f}</td>
            <td>${balance:,.2f}</td>
          </tr>
        </table>

        <div class='net-pay-bar'>
          <div>
            <div class='net-label'>AMOUNT PAID</div>
            <div class='net-amount'>${gross:,.2f}</div>
          </div>
          <div class='net-ytd'>
            <div class='net-label'>YTD PAYMENTS</div>
            <div class='net-ytd-amt'>${ytd_paid:,.2f}</div>
          </div>
        </div>

        <div class='notice'>
          <strong>1099 Vendor — No Tax Withholding.</strong>
          Payments to this vendor are not subject to income tax withholding.
          A Form 1099-NEC will be issued if annual payments exceed $600.
          Vendor is responsible for self-employment tax obligations.
        </div>
        """

        company_line = f"<div class='card-sub'>{e(person.get('company',''))}</div>" if person.get('company') else ""
        left_col = f"""
          <div class='card-label'>Vendor / Subcontractor</div>
          <div class='card-name'>{e(person.get('name','—'))}</div>
          {company_line}
          <div class='info-block'>
            <div class='info-row'><span class='lbl'>Payment Type</span><span>{pay_type_str or 'Contract'}</span></div>
            <div class='info-row'><span class='lbl'>Payment Terms</span><span>{pay_terms_str}</span></div>
            <div class='info-row'><span class='lbl'>QB Type</span><span>1099-NEC Vendor</span></div>
            {f"<div class='info-row'><span class='lbl'>Tax ID</span><span>***{e(person.get('tax_id',''))}</span></div>" if person.get('tax_id') else ''}
          </div>
        """

    doc_type = "PAY STATEMENT" if is_employee else "REMITTANCE ADVICE"
    status_color = {"paid": "#22c55e", "partial": "#60a5fa", "pending": "#f59e0b"}.get(record.get("status",""), "#888")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{'Pay Stub' if is_employee else 'Remittance'} — {e(person.get('name',''))} — {pay_date_fmt}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Barlow+Condensed:wght@700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Inter',sans-serif; background:#f4f4f5; color:#111; font-size:14px; }}
  .page {{ max-width:780px; margin:32px auto; background:#fff; border-radius:12px;
           box-shadow:0 4px 32px rgba(0,0,0,0.12); overflow:hidden; }}
  @media print {{
    body {{ background:#fff; }}
    .page {{ box-shadow:none; margin:0; border-radius:0; max-width:100%; }}
    .no-print {{ display:none !important; }}
  }}

  /* Header */
  .stub-header {{ background:#0a0a0a; padding:22px 28px; display:flex; align-items:center; justify-content:space-between; }}
  .company-block .co {{ font-family:'Barlow Condensed',sans-serif; font-size:22px; font-weight:800;
    color:#fff; letter-spacing:3px; text-transform:uppercase; }}
  .company-block .addr {{ font-size:11px; color:rgba(255,255,255,0.45); margin-top:3px; }}
  .doc-type-block {{ text-align:right; }}
  .doc-type {{ font-family:'Barlow Condensed',sans-serif; font-size:18px; font-weight:800;
    color:#e8650a; letter-spacing:2px; text-transform:uppercase; }}
  .doc-num {{ font-size:10px; color:rgba(255,255,255,0.4); margin-top:4px; letter-spacing:1px; }}

  /* Status bar */
  .status-bar {{ background:#111; padding:8px 28px; display:flex; align-items:center; gap:12px;
    border-bottom:2px solid #e8650a; }}
  .status-dot {{ width:8px; height:8px; border-radius:50%; background:{status_color}; flex-shrink:0; }}
  .status-text {{ font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:{status_color}; }}
  .status-date {{ margin-left:auto; font-size:11px; color:rgba(255,255,255,0.4); }}

  /* Two-col info row */
  .info-row-top {{ display:grid; grid-template-columns:1fr 1fr; gap:0;
    border-bottom:1px solid #e5e7eb; }}
  .info-col {{ padding:20px 28px; }}
  .info-col + .info-col {{ border-left:1px solid #e5e7eb; }}
  .card-label {{ font-size:9px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:#9ca3af; margin-bottom:6px; }}
  .card-name {{ font-size:18px; font-weight:700; }}
  .card-sub {{ font-size:12px; color:#6b7280; margin-top:2px; }}
  .info-block {{ margin-top:12px; }}
  .info-row {{ display:flex; gap:8px; padding:4px 0; font-size:12px;
    border-bottom:1px solid #f3f4f6; }}
  .info-row:last-child {{ border-bottom:none; }}
  .lbl {{ color:#9ca3af; width:110px; flex-shrink:0; font-weight:500; }}

  /* Pay date col */
  .pay-date-card-label {{ font-size:9px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:#9ca3af; margin-bottom:6px; }}
  .pay-date-val {{ font-size:18px; font-weight:700; color:#e8650a; }}
  .job-ref {{ display:inline-block; margin-top:8px; padding:3px 10px;
    background:#fff7ed; border:1px solid #fed7aa; border-radius:6px;
    font-size:11px; font-weight:700; color:#ea580c; }}

  /* Amounts sections */
  .amounts-block {{ padding:20px 28px; }}
  .section-head {{ font-size:10px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:#6b7280; padding:10px 0 6px;
    border-bottom:2px solid #e5e7eb; margin-bottom:2px; margin-top:12px; }}
  .section-head:first-child {{ margin-top:0; }}
  .amt-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .amt-table th {{ padding:8px 10px; text-align:left; font-size:10px; font-weight:700;
    text-transform:uppercase; letter-spacing:0.8px; color:#9ca3af;
    background:#f9fafb; border-bottom:1px solid #e5e7eb; }}
  .amt-table th:not(:first-child) {{ text-align:right; }}
  .amt-table td {{ padding:9px 10px; border-bottom:1px solid #f3f4f6; }}
  .amt-table td:not(:first-child) {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .amt-table tr.subtotal td {{ background:#f9fafb; border-top:2px solid #e5e7eb; }}

  /* Net pay bar */
  .net-pay-bar {{ display:flex; align-items:center; justify-content:space-between;
    background:#0a0a0a; margin-top:16px; padding:18px 20px; border-radius:8px; }}
  .net-label {{ font-size:10px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:rgba(255,255,255,0.5); margin-bottom:4px; }}
  .net-amount {{ font-size:28px; font-weight:800; color:#e8650a;
    font-family:'Barlow Condensed',sans-serif; letter-spacing:1px; }}
  .net-ytd {{ text-align:right; }}
  .net-ytd-amt {{ font-size:20px; font-weight:700; color:#fff;
    font-family:'Barlow Condensed',sans-serif; }}

  /* Notice */
  .notice {{ margin-top:14px; padding:12px 14px; background:#f9fafb;
    border-left:3px solid #e8650a; border-radius:0 6px 6px 0;
    font-size:11px; color:#6b7280; line-height:1.6; }}

  /* Footer */
  .stub-footer {{ background:#f9fafb; border-top:1px solid #e5e7eb;
    padding:14px 28px; display:flex; justify-content:space-between;
    align-items:center; }}
  .footer-left {{ font-size:10px; color:#9ca3af; line-height:1.6; }}
  .footer-right {{ display:flex; gap:8px; }}
  .btn-print {{ padding:9px 20px; background:#e8650a; border:none; border-radius:8px;
    font-size:12px; font-weight:700; color:#fff; cursor:pointer; font-family:inherit;
    letter-spacing:0.5px; transition:background .15s; }}
  .btn-print:hover {{ background:#d05a08; }}
  .btn-close {{ padding:9px 16px; background:#f3f4f6; border:1px solid #e5e7eb;
    border-radius:8px; font-size:12px; font-weight:600; color:#6b7280;
    cursor:pointer; font-family:inherit; transition:all .15s; }}
  .btn-close:hover {{ background:#e5e7eb; }}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="stub-header">
    <div class="company-block">
      <div class="co">{co_name}</div>
      <div class="addr">{co_addr}</div>
    </div>
    <div class="doc-type-block">
      <div class="doc-type">{doc_type}</div>
      <div class="doc-num">REF # {stub_num}</div>
    </div>
  </div>

  <!-- Status bar -->
  <div class="status-bar">
    <div class="status-dot"></div>
    <div class="status-text">{record.get('status','—').upper()}</div>
    <div class="status-date">Payment Date: {pay_date_fmt}</div>
  </div>

  <!-- Info columns -->
  <div class="info-row-top">
    <div class="info-col">
      {left_col}
    </div>
    <div class="info-col">
      <div class="pay-date-card-label">Pay Date</div>
      <div class="pay-date-val">{pay_date_fmt}</div>
      {f'<span class="job-ref">📋 {e(job_num)}</span>' if job_num else ''}
      <div class="info-block" style="margin-top:16px;">
        <div class="info-row"><span class="lbl">Gross Amount</span><span>${amount_due:,.2f}</span></div>
        <div class="info-row"><span class="lbl">Amount Paid</span><span style="color:#22c55e;font-weight:700;">${gross:,.2f}</span></div>
        {'<div class="info-row"><span class="lbl">Balance Due</span><span style="color:#ef4444;font-weight:700;">$'+f'{amount_due-gross:,.2f}'+'</span></div>' if amount_due > gross else ''}
        <div class="info-row"><span class="lbl">Status</span>
          <span style="font-weight:700;color:{status_color};">{record.get('status','—').capitalize()}</span></div>
      </div>
    </div>
  </div>

  <!-- Earnings / Payment detail -->
  <div class="amounts-block">
    {earnings_block}
  </div>

  <!-- Footer -->
  <div class="stub-footer no-print">
    <div class="footer-left">
      {co_name} · Payroll &amp; Accounts Payable<br>
      Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')} · For internal use only
    </div>
    <div class="footer-right">
      <button class="btn-close no-print" onclick="window.close()">Close</button>
      <button class="btn-print" onclick="window.print()">🖨 Print / Save PDF</button>
    </div>
  </div>

</div>
</body>
</html>"""
