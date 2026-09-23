# Part 11G settlement policy

## Approval and scope

The project owner delegated the remaining Phase 11G policy decisions on 23 September 2026. This
document records the resulting product policy as version `1.0.0`.

Automatic calculation covers foreign, full-time employees in the UAE mainland private sector who
remain under the traditional end-of-service gratuity scheme. The service stops with
`settlement_policy_unavailable` for UAE nationals, free-zone records, DIFC or ADGM cases, domestic
workers, alternative savings schemes, missing nationality, and any work pattern that the stored
record cannot support.

The legal basis is Article 51 and Article 53 of Federal Decree-Law No. 33 of 2021, Cabinet Resolution
No. 1 of 2022, and the UAE Government guidance for private-sector end-of-service benefits and annual
leave. The stored policy digest fixes the product interpretation. A law or guidance change requires
a new policy version. Existing settlements keep their original policy and source snapshot.

Official sources:

- [Federal Decree-Law No. 33 of 2021](https://www.uaelegislation.gov.ae/en/legislations/1541/download)
- [Cabinet Resolution No. 1 of 2022](https://www.uaelegislation.gov.ae/en/legislations/1547/download)
- [UAE Government end-of-service guidance](https://u.ae/en/information-and-services/jobs/employment-in-the-private-sector/end-of-service-benefits-for-employees-in-the-private-sector)
- [UAE Government annual-leave guidance](https://u.ae/en/information-and-services/jobs/employment-in-the-private-sector/types-of-leaves-and-entitlements-in-the-private-sector/annual-leave)

## Service and gratuity

Service starts on the employment start date and includes the trusted termination date. The service
subtracts approved unpaid leave recorded wholly within that interval. It uses 365 paid service days
per service year. This day-count convention is a product rule because the cited law does not define
leap-day arithmetic for the calculation.

An employee becomes eligible at 365 paid service days. The daily rate is basic salary divided by 30.
The first 1,825 paid service days accrue 21 gratuity days per 365 days. Later paid service accrues 30
gratuity days per 365 days. Partial years remain proportional. Resignation does not reduce the
amount. The maximum is 24 months of basic salary.

## Leave, payroll, and deductions

Only the current-year leave balance whose type code is `ANNUAL` is encashed. The service multiplies
the nonnegative remaining balance by basic salary divided by 30. A missing balance means zero days.

The final salary source is the approved, generated payslip for the trusted termination month. An
unpaid payslip contributes its net pay. A payslip or payroll run with a payment date contributes
zero. Missing approved payroll blocks settlement.

The service deducts every active salary advance's exact outstanding balance and records a settlement
repayment in the same transaction. An open asset assignment blocks settlement. Asset valuation is
not inferred, so automatic asset deduction is always zero.

Notice pay, notice deduction, other earnings, and other deductions are explicit reviewed inputs. Any
nonzero manual input requires a reason. The browser cannot derive these values from contract text or
asset records.

## Rounding and review

The service uses decimal arithmetic and `ROUND_HALF_UP`. It rounds each monetary component to two
decimal places, then rounds gross earnings, total deductions, and net settlement to two decimal
places. A negative net settlement blocks completion. Phase 11G does not create a receivable or cap a
negative result to zero.

Checklist initialization and settlement completion require different administrators. Completion
recalculates every source under locks and compares the source digest returned by preview. A changed
task, employee, leave, payroll, advance, contract, policy, or manual input causes a state conflict.

## Exact examples

With a basic salary of AED 10,000.00 and no unpaid leave:

| Paid service days | Gratuity |
| ---: | ---: |
| 364 | AED 0.00 |
| 365 | AED 7,000.00 |
| 1,825 | AED 35,000.00 |
| 2,190 | AED 45,000.00 |
| 36,500 | AED 240,000.00 after the cap |

For 366 paid service days, the rounded gratuity is AED 7,019.18. A 7.50-day annual leave balance at
the same basic salary produces AED 2,500.00 leave encashment.
