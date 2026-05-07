# Lightning Bolt API Reference

This document describes the reverse-engineered Lightning Bolt API behavior used by this
project. It is written for developers who need to implement a compatible client in any
language without reading the Python source code.

Lightning Bolt does not publish this API as public documentation. The behavior here comes
from live browser/network investigation and direct replay validation. Treat it as a
working protocol reference, not a vendor-supported contract.

## Scope

This reference covers read-only schedule access:

- authentication and token refresh
- dashboard/session bootstrap
- ViewerAPI schedule reads
- personal schedule reads
- subscription metadata
- derived calendar subscription URLs
- employee activity feed

It does not cover write actions such as shift claims, swaps, schedule edits, request
creation, or note updates.

## Host Map

| Host | Role |
| --- | --- |
| `s2.lightning-bolt.com` | Legacy form login entrypoint. |
| `lblite.lightning-bolt.com` | SPA host and dashboard/session bootstrap API. |
| `lbapi.lightning-bolt.com` | Bearer-token API for ViewerAPI, schedule, token refresh, and subscription metadata. |
| `fd.lightning-bolt.com` | Bearer-token API for employee activity feed. |
| `m.lightning-bolt.com` | Public calendar subscription feed host. |

## Auth Flow

The replayable login flow crosses the `s2`, `lblite`, and `lbapi` hosts.

1. `GET https://s2.lightning-bolt.com/?source=access&dest=app&noRedirect=true&origin=<encoded-origin>`

   Loads the login form and starts the cookie session.

2. `POST` the same URL as form data:

   ```text
   txtUserName=<username>
   txtUserPass=<password>
   submit=<login button value>
   ```

   Follow redirects.

3. Follow the redirect to:

   ```text
   https://s2.lightning-bolt.com/Lblite.aspx?noredirect=true&origin=...
   ```

4. Follow the redirect to:

   ```text
   https://lblite.lightning-bolt.com/login/unity?token=<single-use-token>&origin=...
   ```

   This step sets Lightning Bolt token cookies, including `LB_TKN`.

5. `GET https://lblite.lightning-bolt.com/api/v1/dashboard`

   This confirms the `lblite` session and rotates `LB_TKN` to a fresh refresh-token value.

6. `POST https://lbapi.lightning-bolt.com/token`

   Send form-encoded data:

   ```text
   grant_type=refresh_token
   refresh_token=<current LB_TKN>
   client_id=1bc4e40b-0373-42a8-bfed-979f10b0743a
   ```

   The response includes a bearer JWT and a newly rotated refresh token.

7. Use the JWT for subsequent `lbapi.*` and `fd.*` calls:

   ```text
   Authorization: Bearer <access_token>
   ```

## Required Headers

Always send this origin header to `lbapi.*` and `fd.*` endpoints:

```text
Origin: https://lblite.lightning-bolt.com
```

The server rejects relevant cross-origin API calls without it.

Recommended general headers:

```text
Accept: application/json, text/plain, */*
Accept-Encoding: gzip, deflate
User-Agent: <your-client-name>
```

For `/token`, send:

```text
Content-Type: application/x-www-form-urlencoded
```

For `/viewerapi`, send JSON:

```text
Content-Type: application/json
```

## JWT And Refresh Tokens

The `/token` response uses an OAuth2-style refresh-token grant shape:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3599,
  "refresh_token": "<new-refresh-token>"
}
```

The JWT payload includes identity and expiry fields such as:

```json
{
  "clientID": "1bc4e40b-0373-42a8-bfed-979f10b0743a",
  "customerID": "<customer-id>",
  "empID": "<employee-id>",
  "userID": "<user-id>",
  "userName": "<username>",
  "iss": "https://lbapi.lightning-bolt.com/",
  "aud": "<audience>",
  "nbf": 1770000000,
  "exp": 1770003600
}
```

Clients can parse `exp` without verifying the signature to decide when to refresh. Do not
treat unverified claims as proof of identity outside this client context.

Refresh-token rules:

- Refresh tokens rotate.
- Old refresh tokens are single-use.
- Store the latest refresh token after every `/token` response.
- Serialize refresh attempts inside one process so two concurrent requests do not consume
  the same refresh token.
- Refresh before expiry, for example at `exp - 300` seconds.
- On refresh failure, perform a full login if credentials are available.

## Dashboard Endpoint

```text
GET https://lblite.lightning-bolt.com/api/v1/dashboard
```

Auth: `lblite` cookies from the login chain.

Important behavior:

- Confirms the web session.
- Rotates the `LB_TKN` cookie.
- Returns dashboard/user metadata.
- May return top-level fields as JSON-encoded strings when gzip is not requested.

Defensive parser rule: if a dashboard field is a string that begins with `{` or `[`, try to
JSON-decode it.

Common useful fields:

- user/customer identity
- user timezone
- app availability
- permissions
- views, when available

Some accounts return no useful dashboard views. In that case, call ViewerAPI without
`view_id` to get the default context.

## ViewerAPI Endpoint

```text
POST https://lbapi.lightning-bolt.com/viewerapi
```

Auth: bearer JWT.

Confirmed request body fields:

```json
{
  "view_id": 123,
  "tz": "UTC",
  "start_date": "20260501",
  "end_date": "20260531"
}
```

Rules:

- Only send confirmed fields.
- `view_id` is optional.
- `tz` accepts IANA timezone names.
- `start_date` and `end_date` must be `YYYYMMDD`.
- ISO dates such as `2026-05-01` are silently ignored by Lightning Bolt and should be
  rejected by your client before sending.
- Unknown date field names are silently ignored.

When `view_id` is omitted, Lightning Bolt returns the authenticated user's default viewer
context. This is useful for first-run discovery when the user does not know a view ID.

The response is the main schedule bootstrap payload. It contains the schedule grid plus
metadata needed to interpret it.

Top-level response keys observed:

| Key | Meaning |
| --- | --- |
| `applications` | App availability flags for the current user. |
| `assignment_types` | Assignment type taxonomy. |
| `assignments` | Assignment definitions in the view. |
| `departments` | Department and template metadata. |
| `holidays` | Holidays in the requested range. |
| `locations` | Physical locations, when used by the organization. |
| `permissions` | Feature and department access metadata. |
| `personnel` | Personnel visible in the selected/default view. |
| `personnel_types` | Personnel type taxonomy. |
| `request_data` | Request/swap/preference data visible in the viewer context. |
| `schedule_data` | Flat schedule slot list. |
| `user` | Logged-in user metadata and parameters. |
| `user_personnel` | Logged-in user's personnel record. |
| `user_settings` | Viewer settings such as defaults. |
| `view_context` | Metadata for the current selected/default view. |
| `views` | Other views available to the user, when returned. |

## Schedule Data

The main schedule rows live at:

```text
schedule_data.data[]
```

Each row is a slot record. Common fields:

| Field | Meaning |
| --- | --- |
| `slot_id` | Slot identifier. |
| `slot_uuid` | Slot UUID. |
| `sched_id` | Schedule/publication identifier. |
| `emp_id` | Assigned employee/personnel ID. |
| `display_name` | Assigned person or open-slot display label. |
| `compact_name` | Compact person/open-slot label. |
| `last_name` | Assigned person's last name or open-slot placeholder convention. |
| `template` | Template name. |
| `template_id` | Template ID. |
| `department_id` | Department ID. |
| `slot_date` | Date as `YYYY-MM-DD`. |
| `start_time` | Organization-local start datetime. |
| `stop_time` | Organization-local stop datetime. |
| `start_time_utc` | UTC start datetime. |
| `stop_time_utc` | UTC stop datetime. |
| `assign_id` | Assignment ID. |
| `assign_structure_id` | Assignment structure label or ID. |
| `assign_display_name` | Assignment display name. |
| `assign_compact_name` | Compact assignment name. |
| `is_pending` | Pending/request state flag. |
| `is_granted_request` | Granted request flag. |
| `is_manual_slot` | Manual slot flag. |
| `is_default_time` | Whether default assignment times were used. |
| `note` | Slot note, when present. |
| `request_note` | Request note, when present. |
| `decision_note` | Decision note, when present. |
| `has_note` | Note presence flag. |
| `original_emp_id` | Original assigned employee before reassignment, when available. |
| `modified_by_emp_id` | Employee ID that last modified the slot, when available. |
| `modified_by_display_name` | Display name for the modifier, when available. |
| `modified_date` | Slot modification timestamp, when available. |
| `emp_request_id` | Request identifier, when available. |
| `emp_request_status` | Request status, when available. |
| `is_pending_request` | Request pending flag, when available. |
| `slot_history` | Compact history entries such as swap approval text and timestamps. |
| `has_change` | Change flag. |
| `slot_history` | Historical states when returned. |
| `emp_request_id` | Request ID, when linked. |
| `emp_request_status` | Request status, when linked. |
| `location_ids` | Location IDs. |
| `location_names` | Location names. |
| `work_units` | Work unit value. |
| `tallies` | Tally IDs. |
| `call_order` | Call-order value. |
| `loa_reason_id` | Leave/block reason ID. |
| `loa_reason_name` | Leave/block reason name. |
| `status` | Slot status. |
| `modif_explanation` | Modification explanation. |
| `emp_ptype` | Personnel type ID for the assigned employee. |
| `assign_atype` | Assignment type ID. |
| `parent_assign_structure_id` | Parent assignment structure ID. |
| `national_provider_identifier` | NPI when visible and applicable. |

Preserve the full raw slot object. Lightning Bolt may add organization-specific or
feature-specific fields.

## Interpreting Slot Types

These are read-side interpretations only.

Open shift:

```text
last_name == "z.Administrative"
display_name matches ^OPEN \d+$
```

Assigned to a specific employee:

```text
emp_id == <target-emp-id>
```

Has notes:

```text
has_note == true
or note/request_note/decision_note is non-empty
```

Leave/blocking signals:

```text
loa_reason_id is not null
or loa_reason_name is not null
or status/modification fields indicate a blocked state
```

Provider classification such as MD vs APP is not a protocol concern. Return `emp_ptype`,
`assign_atype`, personnel type metadata, assignment metadata, and templates to the caller.
Do not hardcode organization-specific classification rules in a reusable API client.

## View, Department, Template, Personnel, And Assignment Metadata

ViewerAPI returns enough metadata to avoid scraping UI labels.

`view_context` commonly includes:

- `view_id`
- `name`
- `filter_id`
- theme/settings identifiers
- accessibility metadata
- source filter data

`departments[]` commonly includes:

- department IDs and names
- department/template relationships
- nested templates

`departments[].templates[]` commonly includes:

- `template_id`
- `name`
- `name_full`
- publication date fields such as `first_published_date` and `last_published_date`
- request horizon/window fields when configured

`personnel[]` commonly includes:

- `emp_id`
- display/compact/last/first names
- department IDs
- scheduled/expired flags
- personnel type IDs
- roles
- NPI when visible and applicable

Clients can use `personnel[]` for employee ID discovery. Prefer stable `emp_id` values for
automation; display names can be nicknames or manually formatted by schedulers.

`assignments[]` commonly includes:

- assignment IDs
- structure IDs
- display/compact names
- descriptions
- department/template mappings
- default time maps
- assignment type maps

## Discovery Strategy

A robust client should not require the user to know a view ID.

Recommended discovery order:

1. Call dashboard and use dashboard views if they contain usable nonzero IDs.
2. Use a configured default view ID if the user provided one.
3. Reuse a cached auto-discovered view ID from the session cache.
4. Call ViewerAPI without `view_id`.
5. If the default response appears personal-only, probe bounded read-only candidate view
   IDs and choose the broadest accessible ViewerAPI response.

Schedule and personnel-discovery reads can omit `view_id`. The library should not require
users to know Lightning Bolt's internal view IDs; a configured default view is an override,
not a prerequisite.

## Personal Schedule Endpoint

```text
GET https://lbapi.lightning-bolt.com/schedule/range/
```

Auth: bearer JWT.

Query parameters:

```text
start_date=YYYYMMDD
end_date=YYYYMMDD
listed=true
emp_id=<employee-id>
```

This returns a lighter response for one employee. The slot schema matches
`viewerapi.schedule_data.data[]`.

Use this endpoint when you only need one person's schedule. Use ViewerAPI when you need
view-level metadata or all visible schedule slots.

## Subscription Endpoint

```text
GET https://lbapi.lightning-bolt.com/subscription?emp_id=<employee-id>&dash=true
```

Auth: bearer JWT.

Returns calendar subscription metadata for an employee. Observed fields include
subscription IDs, schedule view/template metadata, timezone, offset/window settings,
checksum-like metadata, and excluded assignments.

The response shape may be a list or an object. Preserve the raw payload.

Lightning Bolt does not return the app-specific subscription URLs directly from this
endpoint. They are derived from the subscription `md5` field:

| App | URL |
| --- | --- |
| iPhone/iPad | `https://m.lightning-bolt.com/{md5}i.ics` |
| Google Calendar | `https://m.lightning-bolt.com/{md5}g.ics` |
| Android | `https://m.lightning-bolt.com/{md5}g.ics` |
| Outlook 2016 and later | `webcal://m.lightning-bolt.com/{md5}o.ics` |
| IBM Lotus Notes | `https://m.lightning-bolt.com/{md5}i.ics` |
| Calendar for Mac/iCal | `https://m.lightning-bolt.com/{md5}i.ics` |

Use the Google/Android `g.ics` URL as the default general-purpose calendar URL. The
Outlook variant intentionally uses the `webcal://` scheme.

## Employee Feed Endpoint

```text
GET https://fd.lightning-bolt.com/employee_feed/<customer-id>/<employee-id>?last=<unix-ts>
```

Auth: bearer JWT.

Returns activity/audit feed items. It can be used for cheap incremental checks before
fetching larger schedule payloads.

Observed feed item concepts include:

- item type
- message
- message arguments
- creator employee ID
- timestamp
- assignment/date/person references in message arguments

Preserve raw feed items because feed shapes may vary by event type.

## Time And Date Rules

Request dates:

- `viewerapi.start_date`
- `viewerapi.end_date`
- `schedule/range start_date`
- `schedule/range end_date`

must be `YYYYMMDD`.

Slot response dates:

- `slot_date` is `YYYY-MM-DD`.
- `start_time` and `stop_time` are organization-local wall-clock timestamps.
- `start_time_utc` and `stop_time_utc` are UTC equivalents.

Do not assume the request `tz` changes slot timestamps. In the investigation, `tz` affected
viewer display behavior but did not change the slot time fields.

For timezone-aware datetime construction, pair local slot timestamps with the organization
timezone from dashboard/user metadata or explicit client configuration.

## Publication Horizons

Templates may include publication horizon fields such as `last_published_date`. Lightning
Bolt may cap results at the published horizon even if the caller requests later dates.

A client should expose template publication metadata and avoid silently promising future
coverage beyond what Lightning Bolt has published.

## Error Handling And Retries

Recommended behavior:

- Parse JWT expiry and refresh before it expires.
- Serialize refresh-token use.
- On a 401 from a bearer-token endpoint, refresh once and retry once.
- If refresh fails and credentials are available, perform a full login.
- Use conservative backoff on 429 or 5xx responses.
- Reject invalid request dates locally before sending them.
- Preserve response headers useful for diagnostics when available.

Observed diagnostic headers include internal Lightning Bolt type/environment headers. They
are useful for debugging but should not be required for normal operation.

## Request Body Discipline

The private API may silently ignore unknown or malformed fields. For ViewerAPI, send only:

- `view_id`
- `tz`
- `start_date`
- `end_date`

Do not infer that a successful response means every field in a request body was honored.
Validate request dates and keep request payloads minimal.

ViewerAPI has no confirmed server-side field projection or result-limit parameter. A broad
view/date-range request may return a large schedule grid plus metadata. Libraries that
serve LLM or MCP clients should summarize ViewerAPI results before returning them.
Use default result caps with pagination metadata, not hard blockers, so advanced callers
can still page or intentionally request full exports.

For employee-specific questions, prefer:

```text
GET https://lbapi.lightning-bolt.com/schedule/range/?start_date=YYYYMMDD&end_date=YYYYMMDD&listed=true&emp_id=N
```

Use broad ViewerAPI reads for coverage, open-shift, and debugging workflows where a full
view is actually needed.

ViewerAPI can return slots outside the requested range because the schedule view expands
to visible calendar weeks. Consumer-facing helpers should filter parsed rows by
`slot_date` after the API call.

Open shifts have been observed as administrative placeholder personnel, commonly
`last_name == "z.Administrative"` with display labels such as `OPEN 1`. MD/APP grouping is
not a first-class API field; use template and assignment labels, with caller-configurable
patterns, and keep unknown rows instead of dropping them.

Pending/request flags are visible when Lightning Bolt includes fields such as
`is_pending`, `is_granted_request`, `request_note`, and `decision_note`. A granted pickup
may be indistinguishable from a normal assigned shift once the slot is finalized; clients
should not infer pickup history without a reliable field in the raw slot.

Provider-to-provider trades are visible when `original_emp_id` differs from `emp_id`.
From the perspective of employee `N`, classify:

- `trade_in`: `emp_id == N` and `original_emp_id` is another employee.
- `trade_out`: `original_emp_id == N` and `emp_id` is another employee.
- `regular`: no reassignment, meaning `original_emp_id` is missing or equals `emp_id`.
- `unknown_reassignment`: reassigned, but no perspective employee matches either side.

Employee-specific `/schedule/range` reads may only include the current employee's visible
assigned slots, so they can miss trade-outs. Use ViewerAPI plus a post-filter on
`original_emp_id` to find both sides of a trade.

## Security And Sanitization

Never log or commit:

- usernames or passwords
- cookies
- refresh tokens
- bearer JWTs
- raw auth responses
- unsanitized dashboard or ViewerAPI captures
- real personnel names or identifiers
- real organization-specific captures

Public fixtures should use synthetic names, synthetic IDs, redacted emails, and redacted
provider identifiers while preserving schema shape.

## Reimplementation Checklist

A new client in another language should implement:

- cookie jar support across `s2` and `lblite`
- form login with redirects enabled
- dashboard call and `LB_TKN` rotation handling
- form-encoded `/token` exchange
- JWT expiry parsing
- refresh-token serialization
- bearer auth headers for `lbapi` and `fd`
- `Origin: https://lblite.lightning-bolt.com`
- strict `YYYYMMDD` request-date validation
- ViewerAPI read with optional `view_id`
- schedule range, subscription, and employee feed reads
- compact schedule summaries for model-facing consumers
- derived calendar subscription URL construction from subscription `md5`
- raw payload preservation
- local session cache that stores auth state only

Keep the first implementation read-only. Write actions require separate endpoint capture,
manual validation, and a different safety review.
