# SPARC Jira Team profile management retro

## Summary

Admins needed an explicit way to maintain Jira Team Ticket Cost Profiles after the initial SPARC-3 rollout. The existing form could create a profile and would update an existing profile when the same Jira Team name was entered, but that behavior was too implicit and offered no removal path.

## What changed

- Added an Admin-only API route to remove a Jira Team Estimation Profile.
- Added Edit and Remove actions to the Estimation Settings Jira Team Ticket Cost Profiles table.
- Edit loads the selected profile into the existing form and changes the submit action to an update.
- Remove prompts for confirmation and deletes only the estimation profile configuration.
- Product Detail ticket/actual rows are not deleted when a profile is removed; matching tickets simply lose calculated estimates until a profile is recreated.
- Updated the product brief to state that Admins can create, edit, and remove Jira Team Estimation Profiles.

## Versioning

- Frontend/interface version: `0.1.113` to `0.1.114`
- Root release version: `0.1.76` to `0.1.77`

## Verification

- Backend focused regression: `104 passed` across `tests/test_access_control_enforcement.py` and `tests/test_services.py`.
- Frontend TypeScript/Vite production build passed with interface version `0.1.114`.

## Notes for future work

- Profile removal is intentionally a hard delete for the estimation config. If future requirements need audit history or effective dating of profile changes, add versioned profile history rather than overloading this MVP table.
- The profile remains independent from SPARC Team rosters and does not control individual-contributor Forecast entry.
