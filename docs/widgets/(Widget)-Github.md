# Github Widget Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `label`             | string  | `'{icon}'` | The format string for the label. You can use placeholders like `{icon}` to dynamically insert icon information. |
| `label_alt`         | string  | `'{data} Notifications'` | The alternative format string for the label. Useful for displaying additional notification details.             |
| `tooltip`           | boolean | `true` | Whether to show the tooltip on hover.                                                                           |
| `update_interval`   | integer | `600` | The interval in seconds to update the notifications. Must be between 60 and 3600.                               |
| `token`             | string  | `""` | The GitHub personal access token.                                                                               |
| `max_notification`  | integer | `30` | The maximum number of notifications to display in the menu.                                                     |
| `notification_dot`  | dict    | `{'enabled': true, 'corner': 'bottom_left', 'color': 'red', 'margin': [1, 1]}` | A dictionary specifying the notification dot settings for the widget. |
| `only_unread`       | boolean | `false` | Whether to show only unread notifications.                                                                      |
| `show_comment_count`| boolean | `false` | Whether to request and display aggregated comment counts for supported notifications.                           |
| `reason_filters`    | list    | `[]` | Optional list of notification reasons to include (e.g. `['mention', 'assign']`). Empty list returns all reasons. |
| `max_field_size`    | integer | `100` | The maximum number of characters in the title before truncation.                                                |
| `menu`              | dict    | `{'blur': true, 'round_corners': true, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0, 'show_categories': true, 'categories_order': []}` | Menu settings for the widget.                                                                                   |
| `icons`             | dict    | `{'issue': '\uf41b', 'issue_closed': '\uf41d', 'pull_request': '\uea64', 'pull_request_closed': '\uebda', 'pull_request_merged': '\uf17f', 'pull_request_draft': '\uebdb', 'release': '\uea84', 'discussion': '\uf442', 'discussion_answered': '\uf4c0', 'checksuite': '\uf418', 'default': '\uea84', 'github_logo': '\uea84', 'comment': '\uf41f'}` | Icons for different types of notifications in the menu.                                                         |
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}` | Animation settings for the widget. |
| `container_shadow`  | dict    | `None` | Container shadow options.                                                                                       |
| `label_shadow`      | dict    | `None` | Label shadow options.                                                                                           |

```yaml
github:
  type: "yasb.github.GithubWidget"
  options:
    label: "<span>\ueba1</span>"
    label_alt: "Notifications {data}" # {data} return number of unread notification
    token: ghp_xxxxxxxxxxx # GitHub Personal access tokens (classic) https://github.com/settings/tokens
    max_notification: 30 # Max number of notification displaying in menu max: 50
    notification_dot:
      enabled: True
      corner: "bottom_left" # Can be "top_left", "top_right", "bottom_left", "bottom_right"
      color: "red" # Can be hex color or string
      margin: [ 1, 1 ] # x and y margin for the dot
    only_unread: false # Show only unread or all notifications; 
    show_comment_count: false # Summarize comment totals for issues, PRs, and discussions
    reason_filters: [] # e.g. ['mention', 'assign'] to limit notifications by reason
    max_field_size: 54 # Max characters in title before truncation.
    update_interval: 300 # Check for new notification in seconds
    menu:
      blur: True # Enable blur effect for the menu
      round_corners: True # Enable round corners for the menu (this option is not supported on Windows 10)
      round_corners_type: "normal" # Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10)
      border_color: "System" # Set the border color for the menu (this option is not supported on Windows 10)
      alignment: "right"
      direction: "down"
      show_categories: false
      categories_order: ["PullRequest", "Issue", "CheckSuite", "Release", "Discussion"]
    label_shadow:
      enabled: True
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```
## Description of Options

- **label:** The format string for the label. You can use placeholders like `{icon}` to dynamically insert icon information.
- **label_alt:** The alternative format string for the label. Useful for displaying additional notification details.
- **icons:** A dictionary specifying the icons for different types of notifications in the menu. All icons have defaults defined in validation. The available keys are:
  - **issue:** The icon for open issue notifications.
  - **issue_closed:** The icon for closed issues.
  - **pull_request:** The icon for open pull request notifications.
  - **pull_request_closed:** The icon for closed pull requests (not merged).
  - **pull_request_merged:** The icon for merged pull requests.
  - **pull_request_draft:** The icon for draft pull requests.
  - **release:** The icon for release notifications.
  - **discussion:** The icon for open discussion notifications.
  - **discussion_answered:** The icon for discussions with an accepted answer.
  - **checksuite:** The icon for check suite notifications.
  - **default:** The default icon for notification types not explicitly handled.
  - **github_logo:** The icon for the GitHub logo (used in empty state).
  - **comment:** The icon that prefixes the comment count badge when `show_comment_count` is enabled.
- **tooltip:** Whether to show the tooltip on hover.
- **update_interval:** The interval in seconds to update the notifications. Must be between 60 and 3600.
- **token:** The GitHub personal access token. GitHub Personal access tokens (classic) https://github.com/settings/tokens you can set `token: env`, this means you have to set YASB_GITHUB_TOKEN in environment variable.
- **max_notification:** The maximum number of notifications to display in the menu, max 50.
- **notification_dot:** A dictionary specifying the notification dot settings for the widget. This will show a dot on the icon (enclosed with the <span> tag).
  - **enabled:** Enable notification dot.
  - **corner:** Set the corner where the dot should appear.
  - **color:** Set the color of the notification dot. Can be hex or string color.
  - **margin:** Set the x, y margin for the notification dot.
- **only_unread:** Whether to show only unread notifications.
- **show_comment_count:** When enabled, the widget performs a single batched GraphQL request to fetch comment totals for issues, pull requests, and discussions. Pull request counts include review threads. The comment count is displayed alongside each notification item.
- **reason_filters:** Optional list of notification reasons to include. Leave empty to show all reasons. Supported values include `assign`, `author`, `comment`, `ci_activity`, `invitation`, `manual`, `mention`, `review_requested`, `security_alert`, `state_change`, `subscribed`, and `team_mention`.
- **max_field_size:** The maximum number of characters in the title before truncation.
- **menu:** A dictionary specifying the menu settings for the widget. It contains the following keys:
  - **blur:** Enable blur effect for the menu.
  - **round_corners:** Enable round corners for the menu (this option is not supported on Windows 10).
  - **round_corners_type:** Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10).
  - **border_color:** Set the border color for the menu (this option is not supported on Windows 10).
  - **alignment:** Set the alignment of the menu (left, right).
  - **direction:** Set the direction of the menu (up, down).
  - **offset_top:** Set the offset from the top of the screen.
  - **offset_left:** Set the offset from the left of the screen.
  - **show_categories:** Toggle grouping notifications by their GitHub type. When enabled, each group renders inside a `.section` container with a `.section-header` label.
  - **categories_order:** Optional list that defines the preferred order of categories when `show_categories` is enabled. Values are case-insensitive and must match GitHub notification types (for example `PullRequest`, `Issue`). Any categories not listed appear after the configured ones. Available categories include `PullRequest`, `Issue`, `CheckSuite`, `Release`, and `Discussion`.
  
  When `show_categories` is enabled, the first and last notification card within each section gains the `.first` and `.last` classes. If categories are hidden, those classes are applied to the first and last items in the flat list instead. Use them to fine-tune spacing or borders.

- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Widget Style
```css
.github-widget {}
.github-widget .widget-container {}
.github-widget .widget-container .label {}
 /* Popup menu*/
.github-menu {}
.github-menu .header {}
.github-menu .footer {}
.github-menu .footer .label {}
.github-menu .contents {} /* Scrollable area containing all notification sections */
.github-menu .contents .section {} /* Container for notification items, wraps all items when categories disabled, or each category group when enabled */
.github-menu .contents .section-header {} /* Category title (e.g., "Issues", "Pull Requests"). Only visible when show_categories is enabled */
.github-menu .contents .item {} /* Individual notification card */
.github-menu .contents .item.first {} /* First item in section or list */
.github-menu .contents .item.last {} /* Last item in section or list */
.github-menu .contents .item.new {} /* Style for unread notification card */
.github-menu .contents .item .title {} /* Title text of notification card */
.github-menu .contents .item .description {} /* Description text of notification card */
.github-menu .contents .item .icon {} /* Default style for icon */
.github-menu .contents .item .icon.issue {} /* Issue icon */
.github-menu .contents .item .icon.issue.closed {}
.github-menu .contents .item .icon.issue.open {}
.github-menu .contents .item .icon.pullrequest {} /* Pull request icon */
.github-menu .contents .item .icon.pullrequest.open {}
.github-menu .contents .item .icon.pullrequest.closed {}
.github-menu .contents .item .icon.pullrequest.merged {}
.github-menu .contents .item .icon.pullrequest.draft {}
.github-menu .contents .item .icon.release {} /* Release icon */
.github-menu .contents .item .icon.discussion {} /* Discussion icon */
.github-menu .contents .item .icon.discussion.answered {}
.github-menu .contents .item .icon.checksuite {} /* Check suite icon */
.github-menu .contents .item .comment-count {} /* Comment label text */
.github-menu .contents .item .comment-icon {} /* Comment icon */
```

## Example Style for the Widget and Menu
```css
.github-menu    {
    background-color:  rgba(17, 17, 27, 0.2);
    max-height: 500px;
    min-height: 500px;
    min-width: 420px;
}
.github-menu .header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 15px;
    font-weight: 400;
    font-family: 'Segoe UI';
    padding: 8px;
    color: white;
    background-color: rgba(17, 17, 27, 0.75);
}
.github-menu .footer {
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    padding: 4px 8px 6px 8px;
    background-color: rgba(17, 17, 27, 0.75);
}
.github-menu .footer .label{
    font-size: 12px;
    font-family: 'Segoe UI';
    color: #9399b2;
}
.github-menu .contents {
    background-color:  rgba(17, 17, 27, 0.2);
}
.github-menu .contents .item {
    min-height: 40px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.075);
}
.github-menu .contents .item:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-bottom: 1px solid rgba(255, 255, 255, 0);
}
.github-menu .contents .item .title,
.github-menu .contents .item .description {
    color: #9399b2;
    font-family: Segoe UI;
}
.github-menu .contents .item .title {
    font-size: 14px;
    font-weight: 600; 
}
.github-menu .contents .item .description {
    font-size: 12px;
    font-weight: 500
}
.github-menu .contents .item.new .title,
.github-menu .contents .item.new .description {
    color: #ffffff
}
.github-menu .contents .item .icon {
    font-size: 16px;
    padding-right: 0;
    padding-left: 8px;
    padding-right: 4px;
    color: #9399b2;
}
.github-menu .contents .item.new .icon {
    color: #3fb950;
}
```

## Preview of the Widget
![GitHub YASB Widget](assets/576054922-dc651bd1-dedc-5786-c62a7ebdca70.png)
