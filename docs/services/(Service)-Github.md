# GitHub

`import Yasb`

GitHub notifications (issues, pull requests, discussions, releases and checks), fetched every `updateInterval`,
with functions to mark them read and to sign in.

Uses `token` if set. Otherwise uses the token from YASB's browser sign-in (`signIn()`), saved in
`%LOCALAPPDATA%\YASB\github_token` and shared by all GitHubNotifications objects without a `token`.

## GitHubNotifications

### Properties

#### token : string

GitHub personal access token that can read notifications, for example from `.env` with
`Environment.value("GITHUB_TOKEN")`. Empty to use the sign-in token.

Default: `""`

#### updateInterval : int

Milliseconds between fetches, 60000 to 3600000.

Default: `300000`

#### maxNotifications : int

Number of notifications to fetch, 1 to 100.

Default: `50`

#### onlyUnread : bool

When `true`, `notifications` lists only unread notifications.

Default: `false`

#### reasonFilters : list&lt;string&gt;

Only notifications with these GitHub reasons, any case, such as `["mention", "review_requested"]`. Empty means
all.

Default: `[]`

#### showCommentCount : bool

When `true`, fetches each notification's comment count for `comment_count` and `details`.

Default: `true`

#### notifications : list `read-only`

Notifications that pass `reasonFilters` and `onlyUnread`, in the order GitHub sends them. Each is an object:

- `id` : string, notification id. Used by `markRead()` and `openNotification()`.
- `repository` : string, such as `"amnweb/yasb"`.
- `title` : string, title of the issue, pull request or release.
- `type` : string, subject type: `Issue`, `PullRequest`, `Discussion`, `Release`, `CheckSuite` and others.
- `url` : string, github.com page it opens.
- `unread` : bool, `true` when unread.
- `reason` : string, why you got it, such as `mention`.
- `updated_at` : string, last change time, as GitHub sends it.
- `comment_count` : int, number of comments. `null` without `showCommentCount` or when GitHub doesn't say.
- `statusKey` : string, state: `issue-open`, `issue-closed`, `pr-open`, `pr-draft`, `pr-merged`, `pr-closed`,
  `discussion`, `discussion-answered`, `release`, `checks`, or `unknown`.
- `statusLabel` : string, the state in words, such as `"Merged pull request"`.
- `details` : string, repository, reason and comment count in one line, such as
  `"amnweb/yasb · Mentioned · 3 comments"`.

#### unreadCount : int `read-only`

Number of unread notifications that pass `reasonFilters`, regardless of `onlyUnread`.

#### loading : bool `read-only`

`true` while fetching.

#### error : string `read-only`

Error from the last fetch or sign-in, such as `"Could not connect to GitHub."`. `""` when none.

#### needsSignIn : bool `read-only`

`true` when there is no token, or GitHub rejected the sign-in token.

#### authBusy : bool `read-only`

`true` while `signIn()` waits for the user to approve YASB on GitHub.

#### authCode : string `read-only`

Code to enter on GitHub's page during sign-in. `""` otherwise.

### Functions

#### refresh()

Fetches notifications now.

#### markRead(id: string)

Marks the notification read, in YASB and on GitHub.

#### markAllRead()

Marks all notifications read. With `reasonFilters`, only those that pass the filter.

#### openNotification(id: string)

Opens the notification in the browser and marks it read.

#### signIn()

Starts the GitHub device sign-in. `authBusy` becomes `true` and `authCode` holds the code to enter on GitHub's page
(open it with `openSignInPage()`). After approval, the token is saved and notifications are fetched. On failure,
`error` is set.

#### cancelSignIn()

Cancels a waiting sign-in.

#### openSignInPage()

Opens GitHub's page where `authCode` is entered.

#### copyCode()

Copies `authCode` to the clipboard.

## Used by

YASB's own GitHub widget, listed in [Widgets](./Widgets).
