# Lightning Bolt API Investigation Findings

Source: live investigation performed on 2026-05-06 using Chrome DevTools MCP and direct
replay validation with Python urllib. Raw captures with PII were intentionally left out of
this repo. The fixture copied here has been further anonymized for public use.

## Headline Findings

- DOM scraping is unnecessary for read use cases.
- A single `POST https://lbapi.lightning-bolt.com/viewerapi` returns the full viewer state:
  schedule slots, departments, templates, assignments, personnel, holidays, view context,
  settings, permissions, and request data.
- Auth is replayable without a browser:
  form login on `s2.lightning-bolt.com`, cookie redirects, dashboard call that rotates
  `LB_TKN`, then refresh-token exchange at `/token` for a 1-hour JWT.
- Date params are `YYYYMMDD` only. ISO strings such as `2026-06-01` are silently ignored by
  Lightning Bolt and must be rejected by this library.
- The dashboard endpoint can return top-level JSON fields as JSON-encoded strings unless
  gzip is requested. The parser should request gzip and defensively decode string fields
  beginning with `{` or `[`.
- `Origin: https://lblite.lightning-bolt.com` is required for API calls.

## Auth Flow

The confirmed login chain:

1. `GET https://s2.lightning-bolt.com/?source=access&dest=app&noRedirect=true&origin=...`
2. `POST` same URL with `txtUserName`, `txtUserPass`, and `submit`.
3. Follow redirect to `/Lblite.aspx?noredirect=true&origin=...`.
4. Follow redirect to `https://lblite.lightning-bolt.com/login/unity?token=...&origin=...`.
5. `GET https://lblite.lightning-bolt.com/api/v1/dashboard`, which confirms session and
   rotates `LB_TKN`.
6. `POST https://lbapi.lightning-bolt.com/token` with form body:
   `grant_type=refresh_token&refresh_token=<LB_TKN>&client_id=1bc4e40b-0373-42a8-bfed-979f10b0743a`.
7. Use `Authorization: Bearer <jwt>` for `lbapi.*` and `fd.*`.

JWT payload includes `customerID`, `empID`, `userID`, `userName`, issuer, audience, `nbf`,
and `exp`. TTL is one hour.

Refresh tokens rotate and are single-use. Serialize refreshes with a lock and store the
latest returned refresh token. If refresh fails, do a full login when credentials exist.

## Endpoints

### Auth/session

- `GET/POST s2.lightning-bolt.com/?source=access&dest=app&noRedirect=true&origin=...`
- `GET lblite.lightning-bolt.com/api/v1/dashboard`
- `POST lbapi.lightning-bolt.com/token`
- `GET lbapi.lightning-bolt.com/user/check_token`

### Main viewer endpoint

`POST https://lbapi.lightning-bolt.com/viewerapi`

Body:

```json
{
  "view_id": 123,
  "tz": "UTC",
  "start_date": "20260501",
  "end_date": "20260531"
}
```

Notes:

- `view_id` can be omitted for the "Me" view behavior.
- `tz` accepts IANA names but did not change slot timestamps in the investigation; slot
  timestamps appeared to be organization-local wall-clock values.
- The server caps data at publication horizons. Respect template `last_published_date`.

### Other read endpoints

- `GET lbapi.lightning-bolt.com/schedule/range/?start_date=YYYYMMDD&end_date=YYYYMMDD&listed=true&emp_id=N`
- `GET lbapi.lightning-bolt.com/subscription?emp_id=N&dash=true`
- `GET fd.lightning-bolt.com/employee_feed/{customer_id}/{emp_id}?last=<unix_ts>`

## ViewerAPI Response Shape

Important top-level keys:

- `applications`
- `assignment_types`
- `assignments`
- `departments`
- `holidays`
- `locations`
- `permissions`
- `personnel`
- `personnel_types`
- `request_data`
- `schedule_data`
- `user`
- `user_personnel`
- `user_settings`
- `view_context`
- `views`

`schedule_data.data[]` is the main slot list. Observed fields include:

- `slot_id`, `slot_uuid`, `sched_id`
- `emp_id`, `display_name`, `compact_name`, `last_name`
- `template`, `template_id`, `department_id`
- `slot_date`
- `start_time`, `stop_time`
- `start_time_utc`, `stop_time_utc`
- `assign_id`, `assign_structure_id`, `assign_display_name`, `assign_compact_name`
- `is_pending`, `is_granted_request`, `is_manual_slot`, `is_default_time`
- `note`, `request_note`, `decision_note`, `has_note`, `has_change`
- `modified_by_emp_id`, `modified_by_display_name`, `modified_date`
- `slot_history`
- `emp_request_id`, `emp_request_status`, `emp_request_requested_at`
- `location_ids`, `location_names`
- `work_units`, `tallies`, `call_order`
- `loa_reason_id`, `loa_reason_name`
- `status`, `modif_explanation`
- `emp_ptype`, `assign_atype`, `parent_assign_structure_id`
- `national_provider_identifier`

## Useful Interpretations

- Open shift: `last_name == "z.Administrative"` and `display_name` matches `^OPEN \d+$`.
- Assigned to a user: `emp_id == <target emp_id>`.
- Notes: `has_note == true` and/or any of `note`, `request_note`, `decision_note`.
- Pending swap/request state: `is_pending == true` and related pending/request fields.
- Leave/blocking may appear through `loa_reason_id`, `loa_reason_name`, or blocked display
  conventions.

These are read-side helpers only. Do not encode downstream provider classification here.
