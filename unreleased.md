# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Content Filters**: Added AutoMod-style rules for Disguised Links, URL Shorteners, Mobile Links, Banned Domains, Spam, and Profanity.
- **Web Interface**: Added a Flask web app to view moderation logs (`web.py`).
- **Authentication**: Added "Login with Reddit" to the web interface. Only moderators can view logs.
- **Logging**: Implemented database logging for all moderation actions.
- **Config Editor**: Added web-based editor for `automod.yaml`.
- **Syntax Highlighting**: Added CodeMirror to the config editor for YAML syntax highlighting.
- **Backup**: Automatically creates a backup (`automod.yaml.bak`) before saving changes in the config editor.
- **Restore**: Added a button to restore the configuration from the backup file.
- **Dark Mode**: Implemented a dark mode toggle for the web interface (defaulting to dark).
- **Pagination**: Added pagination to the mod action log (50 items per page).
- **Search**: Added a search bar to filter logs by username or action type.
- **Export**: Added CSV export functionality for filtered logs.
- **Test Mode**: Added `TEST_MODE` env var to simulate bot actions without affecting Reddit.
- **Configurable Tiers**: Moved karma tiers to `tiers.yaml` and added a tab in the config editor to modify them.
- **Stats Page**: Added a visualization page (`/stats`) showing action distribution and activity over time.
- **Stats Filter**: Added a date range picker to the stats page to filter data.
- **Top Offenders**: Added a table to the stats page showing the top 10 users with the most removals.
- **Live Ticker**: Added a "Recent Actions" ticker to the dashboard that auto-refreshes every 5 seconds.
- **Mod Queue**: Added a page to view and act on reported posts and comments.
- **User Notes**: Added a feature to store and manage notes about specific users.
- **Queue Notes**: Automatically displays user notes in the Mod Queue if they exist for the author.
- **Queue Filter**: Added ability to filter Mod Queue by Submissions or Comments.
- **Queue Sort**: Added ability to sort Mod Queue by Newest or Oldest.
- **Report Reasons**: Updated Mod Queue to display report reasons more prominently.
- **Ignore Reports**: Added button to approve items and ignore future reports in Mod Queue.
- **Highlight Reports**: Items with 4 or more reports are now highlighted in the Mod Queue.
- **Ban User**: Added a "Ban User" button and modal to the Mod Queue.
- **Expand Content**: Added ability to expand/collapse long comments and submission bodies in the Mod Queue.
- **Modmail**: Added a page to read and reply to modmail conversations.
- **Modmail Archive**: Added ability to archive and unarchive modmail conversations.
- **Modmail Notes**: Highlights modmail conversations from users who have user notes.

### Changed

### Fixed