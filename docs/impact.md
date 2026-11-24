# Impact, Sustainability and Scalability

**BFB321 – Pharmaceutical Stock Level Tracker**  
**Group 14**

## 1. Impact Evaluation

The Pharmaceutical Stock Level Tracker aims to improve inventory
visibility, replenishment decisions and pharmaceutical stock management.

To evaluate the potential impact of the application, three key
performance indicators (KPIs) were selected:

- Unfulfilled demand
- Expired stock
- Demand forecast error

As verified historical data from an operational pharmacy was not
available, controlled theoretical scenarios were developed to compare
traditional inventory management methods with the supply chain
principles implemented in the application.

The results represent simulated performance and should not be
interpreted as measured improvements from an actual pharmacy.

## 2. Before and After Methodology

The baseline scenario represents traditional inventory management
methods before the introduction of the proposed application.

The improved scenario represents the inventory management principles
supported by the application.

Both scenarios use identical input data within each comparison to
ensure that differences in performance can be attributed to the
inventory management method being evaluated.

The comparison calculations are implemented in `models/impact.py`,
with the results displayed on the application's KPI page.

### 2.1 Unfulfilled Demand

Unfulfilled demand measures the number of product units requested
that cannot be supplied due to insufficient available inventory.

**Before implementation:**

A reactive replenishment policy is applied, where an order is
placed once available inventory is depleted.

**After implementation:**

A proactive replenishment policy is applied, where an order is
placed when the inventory position reaches a predefined reorder point.

#### Scenario assumptions

| Parameter | Value |
|---|---|
| Evaluation period | 14 days |
| Initial inventory | 50 units |
| Replenishment quantity | 60 units |
| Supplier lead time | 3 days |
| Baseline reorder point | 0 units |
| Improved reorder point | 55 units |
| Demand | Identical daily demand for both scenarios |

The improved reorder point of 55 units is an assumed scenario
parameter rather than a value calculated from actual pharmacy data.

#### Calculation

Unfulfilled demand = Requested demand - Fulfilled demand

Total unfulfilled demand is accumulated across the evaluation period.

A lower value indicates improved inventory availability.

The scenario assumes that unfulfilled demand is lost rather than
backordered.

### 2.2 Expired Stock

Expired stock measures the number of pharmaceutical units that
reach their expiry dates before being dispensed.

**Before implementation:**

First-In-First-Out (FIFO) dispensing is applied, prioritising
batches according to their receipt sequence.

**After implementation:**

First-Expiry-First-Out (FEFO) dispensing is applied, prioritising
batches according to their expiry dates.

#### Scenario assumptions

| Batch | Receipt Sequence | Expiry Day | Quantity |
|---|---:|---:|---:|
| Batch A | 1 | 20 | 50 units |
| Batch B | 2 | 5 | 40 units |

Additional assumptions:

- Both batches are available at the beginning of the evaluation.
- The receipt sequence determines FIFO priority.
- Daily demand is 10 units.
- The evaluation period is 10 days.
- Expired stock is removed before dispensing on its expiry day.
- No additional stock is received during the evaluation period.

#### Calculation

Expired stock = Sum of remaining units reaching their expiry dates

A lower value indicates improved pharmaceutical stock utilisation
and reduced potential wastage.

### 2.3 Demand Forecast Error

Demand forecast accuracy is evaluated using Mean Absolute Error
(MAE).

**Before implementation:**

A naive forecasting method is applied, using the previous period's
actual demand as the forecast for the next period.

**After implementation:**

A three-period moving average is applied to reduce the influence
of short-term demand fluctuations.

#### Scenario assumptions

- Both forecasting methods use the same illustrative demand history.
- Forecasts are evaluated over identical periods.
- Only historical observations available before each forecast
  are used.
- The moving average window consists of three periods.

#### Calculation

MAE = Sum of absolute forecast errors / Number of forecasts

Absolute forecast error = |Actual demand - Forecast demand|

A lower MAE indicates greater forecasting accuracy for the
evaluated dataset.

The relative performance of forecasting methods may differ under
other demand patterns.

## 3. KPI Improvement Calculation

The percentage reduction for each KPI is calculated as:

Percentage reduction = ((Before - After) / Before) x 100

A positive percentage indicates a reduction in the KPI value.

A negative percentage indicates deterioration in performance.

If the baseline value is zero, percentage reduction is undefined
and is displayed as N/A.

The application presents the calculated KPI results using a
comparison table and individual horizontal bar charts.

Each chart is scaled independently to support meaningful
comparison between its baseline and improved values.

## 4. Interpretation of Results

Proactive replenishment can reduce unfulfilled demand by
initiating replenishment before inventory is depleted.

FEFO dispensing can reduce pharmaceutical expiry by prioritising
products with the shortest remaining shelf life.

Moving average forecasting can improve demand estimation where
historical demand fluctuates around a relatively stable level.

These potential benefits support the original project objectives
of improved inventory visibility, stock availability and informed
replenishment decisions.

The scenarios demonstrate the relevant supply chain principles
but do not constitute a full operational validation of the
application's existing inventory and forecasting functions.

## 5. Scalability

### 5.1 Multi-Site Inventory Management

The application could be extended to support multiple pharmacy
branches.

A pharmacy or location entity could be introduced into the
database, with inventory batches and stock movements associated
with their respective locations.

This would allow:

- Branch-specific stock visibility.
- Location-specific reorder points.
- Independent demand forecasting per pharmacy.
- Centralised reporting across multiple branches.
- Stock transfers between pharmacy locations.

The current database structure would require further development
to support location-specific inventory management.

### 5.2 Multi-User and Role-Based Access

As the number of users increases, role-based access control
could be introduced or expanded.

| User Role | Proposed Responsibilities |
|---|---|
| Pharmacist | View inventory and record dispensing |
| Inventory Manager | Manage replenishment, suppliers and stock receipts |
| Administrator | Manage users, permissions and system configuration |

Authentication, authorisation and user activity tracking would
need to be implemented or verified before operational deployment.

### 5.3 Database Scalability

The MySQL relational database provides a structured foundation
for managing increasing volumes of pharmaceutical inventory data.

Potential scalability improvements include:

- Indexing frequently searched database columns.
- Optimising database queries.
- Using pagination when retrieving large datasets.
- Implementing database connection pooling.
- Archiving historical stock movement records.
- Performing regular database backups.

The REST API already supports pagination on selected endpoints,
which reduces the amount of data retrieved in individual requests.

Large-scale database performance has not yet been validated
through load testing.

### 5.4 Application Architecture

The application follows a modular architecture separating:

- Frontend templates and static resources.
- Flask routes and REST API endpoints.
- Database connection and transaction management.
- Supply chain models.
- Business services.
- Automated testing.

This separation improves maintainability and allows individual
components to be extended without redesigning the entire system.

### 5.5 Hosting and Deployment

The application could be deployed on a dedicated server or cloud
hosting platform to support access by multiple pharmacies.

A production deployment would require:

- A production-ready WSGI server.
- Secure HTTPS communication.
- Secure management of environment variables.
- Database backups and recovery procedures.
- System monitoring and error logging.
- Appropriate authentication and access control.
- Performance and security testing.

The Flask development server is suitable for academic development
and demonstration but is not intended for production deployment.

## 6. Sustainability

### 6.1 Economic Sustainability

Improved inventory management may reduce:

- Financial losses associated with expired pharmaceuticals.
- Unnecessary investment in excess inventory.
- Emergency replenishment requirements.
- Lost sales resulting from insufficient stock.

### 6.2 Environmental Sustainability

Reducing pharmaceutical expiry may decrease the quantity of
medicine requiring disposal.

More effective replenishment planning may also reduce unnecessary
ordering and transportation requirements.

These environmental benefits are potential outcomes and have
not been quantified in this evaluation.

### 6.3 Operational Sustainability

Centralised inventory information and consistent replenishment
methods support more informed and repeatable operational decisions.

The modular application structure and supporting documentation
also facilitate future maintenance and development.

## 7. Limitations

The following limitations apply to the impact evaluation:

- The scenario data is illustrative rather than actual pharmacy data.
- The evaluation periods are limited.
- The replenishment scenario assumes a constant supplier lead time.
- The improved reorder point is an assumed scenario parameter.
- Forecasting performance depends on the underlying demand pattern.
- Actual financial and environmental savings have not been measured.
- Multi-site deployment has not been validated.
- Large-scale application performance has not been tested.
- Operational use would require additional security and reliability
  assessments.

## 8. Conclusion

The Pharmaceutical Stock Level Tracker demonstrates how inventory
management principles can be integrated into a web-based
decision-support system.

Controlled comparisons provide an illustrative evaluation of
proactive replenishment, FEFO dispensing and demand forecasting.

The modular architecture and relational database provide a
foundation for future scalability, while further operational
validation would be required before implementation in an actual
pharmacy environment.