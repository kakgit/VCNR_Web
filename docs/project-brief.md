# Cine Vault Project Brief

This file is the working product brief for Cine Vault.
It is meant to be updated as decisions change, new modules are added, or priorities shift.

## 1. Product Vision

Cine Vault is a premium entertainment platform for early movie and video-content discovery, reservation, controlled preview access, and catalog management.

The main vision is:

- Reduce and eventually eliminate piracy as much as practically possible
- Release content through the Cine Vault app alongside theatrical release where applicable
- Give creators a direct-to-audience path without depending fully on traditional middle layers
- Help creators recover expected revenue before release through audience-backed reservation demand
- Lower the effective content cost per viewer while improving confidence for creators

The platform is planned to support:

- Movies
- Web series
- TV shows
- Short films
- Related promotional media such as posters, music, and previews

The core business idea is to help content owners measure audience demand before release and collect early reservation intent before content moves into full public release.

The broader strategic idea is to reduce dependence on:

- Traditional distribution middlemen
- Theatre rental dependency for digital release decisions
- Delayed revenue visibility before launch

The product should aim to become a one-stop platform for creators to:

- showcase upcoming projects
- test audience interest
- collect advance reservation value
- decide whether to release digitally in the app

## 2. Main User-Facing Concept

Content begins in an early discovery state and moves through staged visibility in the platform.

Primary content stages:

- Upcoming
- New Released
- Old Movies / Library

For unreleased content in the Upcoming section, users can:

- View posters
- View teasers
- View trailers
- View music and supporting details
- View brief story information
- View genre, language, grade, and category details
- Mark `Wish To Watch`
- Use `Reserve Now`

This helps the content side understand:

- Demand before release
- Interest by title
- Estimated revenue before release
- Reservation-driven momentum before theatrical or official public launch
- How many viewers watched the trailers and promotional material
- How many viewers are interested in watching on release day

## 3. Business Goals

The platform should help teams answer:

- How many users want to watch a title before release?
- How many users are reserving access early?
- What expected revenue can be estimated before launch?
- Which titles are gaining momentum fastest?
- Which categories should be featured more prominently?

The business should also make the following possible:

- Allow creators to activate `Reserve Now` only when they are ready
- Let creators collect value in the form of stars from viewers before release
- Let creators compare actual early demand against target revenue
- Let creators decide whether to release inside the app based on demand, reviews, and collected value
- Let creators cancel app release if targets are not met or plans change
- Automatically release blocked stars back to viewers if release is cancelled

The long-term goal is to make Cine Vault both a discovery platform and a pre-release revenue intelligence platform.

## 4. Planned Content Types

The app should not be limited to only theatrical movies.

Planned supported content families:

- Feature films
- Web series
- TV shows
- Short films
- Promotional assets
- Teasers
- Trailers
- Music related to titles
- Poster galleries and artwork

Because of this, the term `Creator` is currently preferred over `Producer` in the user-facing app.

## 4D. Content Categories

Current primary content categories:

- Movies
- Web Series
- TV Shows

Additional recommended categories for future support:

- Short Films
- Documentaries
- Music Videos
- Specials
- Kids Content

Notes:

- Categories should be manageable from the admin panel
- These categories are top-level content classifications
- Each title should belong to one primary category
- Categories should later be usable in search, filtering, navigation, and homepage layout

Admin expectations for category management:

- Add new categories
- Edit existing categories
- Deactivate unused categories
- Control display order if needed
- Keep the category structure clear for viewers and creators

## 4E. Stage Structure Under Each Category

Each top-level category should contain the following main platform stages:

- Upcoming
- Released
- Library

This means the structure is intended to work like:

- Movies -> Upcoming / Released / Library
- Web Series -> Upcoming / Released / Library
- TV Shows -> Upcoming / Released / Library

Future categories should follow the same pattern unless a later business rule requires a special case.

## 4F. Availability Model By Stage

### Upcoming

Upcoming titles may contain:

- Wish To Watch titles
- Reserve Now titles

Meaning:

- Some upcoming titles may only collect interest through `Wish To Watch`
- Some upcoming titles may allow both interest collection and reservation through `Reserve Now`

### Released

Released titles may contain:

- Owned titles
- Pay Now titles

Meaning:

- `Owned` means the viewer already has entitlement to access the title
- `Pay Now` means the viewer can directly purchase or unlock access after release

### Library

Library titles may contain:

- Free with Ads titles
- Pay Now titles

Meaning:

- `Free with Ads` titles can be watched with advertising-supported access
- `Pay Now` titles remain monetized for viewers who want access without owning them already

## 4G. Catalog Model Summary

Current intended catalog hierarchy:

1. Category
2. Stage
3. Availability type

Example:

- Movies -> Upcoming -> Wish To Watch / Reserve Now
- Movies -> Released -> Owned / Pay Now
- Movies -> Library -> Free with Ads / Pay Now

This same model should also apply to:

- Web Series
- TV Shows
- Future content categories added later

## 4H. Title Metadata Structure

Current title-level content fields should include:

- Title name
- Optional caption
- Category
- Genres
- Languages
- Grade
- Release date
- Tentative release date for upcoming titles
- Story text
- Optional duration
- Cast
- Optional production house
- Posters
- Trailer or teaser

Field rules:

- `Title name` is the main movie or content name
- `Caption` is optional, because some titles may use a supporting tagline or caption and some may not
- `Genres` should be multi-select from the managed genre list
- `Languages` should be multi-select from the managed language list
- `Grade` should be single-select from the managed grade list
- `Release date` should be used for released titles or confirmed release schedules
- `Tentative release date` should be available for upcoming titles before final confirmation
- `Duration` should be an optional text field
- `Cast` should be a textarea so creators or admins can enter the full star cast in one go
- `Production house` should be optional
- `Country` is not required for now

## 4I. Poster Structure

Each title may have multiple posters.

Poster groups should include:

- Horizontal posters
- Vertical posters

Display rule:

- If the current viewer section uses a horizontal poster layout, the app should randomly pick from the title's horizontal poster set
- If the current viewer section uses a vertical poster layout, the app should randomly pick from the title's vertical poster set

This means poster assets should later be organized in a way that allows:

- multiple posters per title
- poster orientation tagging
- random selection by orientation
- use in detail pages, banners, cards, and featured layouts

## 4J. Trailer / Teaser And Detail Page Behavior

Current direction:

- For now, either a teaser or a trailer is enough for a title
- A separate teaser and trailer are not both required in Phase 1

Viewer behavior:

- When the viewer clicks the poster, the app should open the title detail page
- On that detail page, the viewer should be able to see:
  - all posters
  - trailer or teaser
  - story text
  - title details such as genre, language, grade, and release information

This detail page should become the main content information surface before reservation or purchase decisions.

## 4K. Audio And Subtitle Design Direction

Current requirement:

- While the video is playing, the user should be able to change audio language and subtitle language from the player area itself

Recommended implementation direction:

- Treat `audio languages` and `subtitle languages` as media tracks, not as top-level content categories
- Keep them linked to the main title or episode as selectable playback assets

Recommended model:

- `Languages` = general title discovery metadata used in forms, search, and filters
- `Audio languages` = actual playable audio tracks attached to the video asset
- `Subtitle languages` = subtitle track files attached to the video asset

Why this is better:

- Search/filter can use the title language metadata
- Playback controls can use the real media-track lists
- A single title can have one or many audio tracks and one or many subtitle tracks
- This keeps the catalog model clean without turning playback options into categories

Player behavior later:

- The video player should show an audio selector
- The video player should show a subtitle selector
- Users should be able to switch tracks during playback without leaving the player

Suggested data model direction:

- Store one or more audio-track records for a title
- Store one or more subtitle-track records for a title
- Each track should have language information and file-path or media-path information

## 4L. Content Folder Structure

Current preferred storage direction:

- Each content item should have its own main folder

Suggested folder layout per title:

```text
content-root/
  <content-slug>/
    posters/
      horizontal/
      vertical/
    music/
    trailers/
    content/
    subtitles/
    audio/
```

Meaning:

- `posters/horizontal/` stores horizontal posters
- `posters/vertical/` stores vertical posters
- `music/` stores title-related music assets
- `trailers/` stores teaser or trailer media
- `content/` stores the main movie, web series, or TV show media
- `subtitles/` stores subtitle track files
- `audio/` stores alternate audio tracks if separate track delivery is used

This structure should make it easier to:

- organize assets by title
- identify poster orientation clearly
- attach music assets per title
- attach subtitle and audio track options later
- support title detail pages and playback options cleanly

## 4M. Database Storage Direction For Assets

Current recommended approach:

- The database should not store large media files directly
- The database should store metadata and asset-path references

Recommended DB pattern:

- Store title metadata in title tables
- Store folder paths or asset records in related media tables
- Store file-path references for posters, trailers, subtitles, audio tracks, and content files

This is better than storing only one raw folder path because:

- multiple posters need separate tracking
- horizontal and vertical assets need orientation metadata
- trailers, subtitles, and audio tracks may be multiple per title
- future search and admin editing become easier

Recommended practical structure in the DB:

- one main title record
- one or more poster records
- one or more music records
- one or more trailer records
- one or more content-file records
- one or more subtitle-track records
- one or more audio-track records

So:

- folders exist on storage
- DB stores the asset metadata and relative paths
- the app uses DB records to know what to display and play

## 4N. Suggested Title Schema

This section describes the recommended title-level schema in product terms before final DB implementation.

### Main Title Record

Recommended fields:

- id
- title_name
- caption
- category_id
- stage
- availability_type
- story_text
- duration_text
- cast_text
- production_house
- grade_id
- release_date
- tentative_release_date
- creator_id
- reserve_star_price
- reserve_enabled
- cancellation_lock_days
- expected_revenue_target
- current_reserved_stars
- current_wish_count
- status
- created_at
- updated_at

Field meaning:

- `title_name`: main content name
- `caption`: optional supporting tagline
- `category_id`: Movies, Web Series, TV Shows, and future categories
- `stage`: Upcoming, Released, or Library
- `availability_type`: Wish To Watch, Reserve Now, Owned, Pay Now, Free with Ads, depending on stage rules
- `story_text`: main story or brief narrative text
- `duration_text`: optional text field for runtime or episode length
- `cast_text`: free-entry cast text area
- `production_house`: optional
- `grade_id`: one selected grade
- `release_date`: confirmed release date
- `tentative_release_date`: optional upcoming-date estimate
- `creator_id`: owning creator account
- `reserve_star_price`: stars needed if reservation is enabled
- `reserve_enabled`: whether reservation is active
- `cancellation_lock_days`: creator-selected cutoff within platform rules
- `expected_revenue_target`: creator target for release decision
- `current_reserved_stars`: running total of blocked/committed stars
- `current_wish_count`: viewer interest count
- `status`: draft, under review, approved, published, cancelled, archived, and similar future workflow states

### Title-Genre Mapping

Because each title can have multiple genres, use a mapping structure:

- title_id
- genre_id

This is better than one comma-separated field because:

- search becomes easier
- filters become easier
- admin editing becomes cleaner

### Title-Language Mapping

Because each title can have multiple languages, use a mapping structure:

- title_id
- language_id
- language_type

Suggested `language_type` direction for future support:

- primary
- dubbed_audio_available
- subtitle_available

This can later evolve if we want a cleaner split between discovery metadata and playback track metadata.

## 4O. Suggested Media Schema

### Poster Records

Recommended poster fields:

- id
- title_id
- relative_path
- orientation
- label
- is_active

Suggested orientation values:

- horizontal
- vertical

Optional future label values:

- hero
- detail
- card
- campaign

### Trailer / Teaser Records

Recommended trailer fields:

- id
- title_id
- relative_path
- media_type
- is_primary
- is_active

Suggested media types:

- teaser
- trailer

For Phase 1, one active teaser or trailer is enough.

### Music Records

Recommended music fields:

- id
- title_id
- relative_path
- music_type
- label
- is_primary
- is_active

Suggested `music_type` values:

- song
- theme
- soundtrack
- background_score

Music can later be used in:

- title detail pages
- promo sections
- preview campaigns
- creator-uploaded promotional assets

### Main Content File Records

Recommended content-file fields:

- id
- title_id
- relative_path
- content_part_type
- episode_number
- season_number
- is_primary
- is_active

Suggested `content_part_type` values:

- main_feature
- episode
- bonus

Suggestion:

- Even if Phase 1 starts mostly with movies, keeping optional season and episode support now will help avoid reworking the schema later for web series and TV shows.

### Subtitle Track Records

Recommended subtitle-track fields:

- id
- title_id
- content_file_id
- language_id
- relative_path
- format
- is_default
- is_active

Suggested subtitle formats for future player compatibility:

- WebVTT preferred for web and app player support
- SRT can be supported at ingest time and converted if needed

### Audio Track Records

Recommended audio-track fields:

- id
- title_id
- content_file_id
- language_id
- relative_path_or_track_key
- track_mode
- is_default
- is_active

Suggested `track_mode` values:

- separate_file
- embedded_track
- stream_variant

This gives flexibility for future playback implementation depending on the final mobile player and streaming format.

## 4R. Suggested Database Entities

Below is the recommended first-pass entity model for implementation.

### Core access and accounts

- users
- user_profiles
- creator_profiles
- advertiser_profiles
- sessions

Purpose:

- `users` stores sign-in identity, role, status, and security-level account data
- `user_profiles` stores display and personal profile data
- `creator_profiles` stores creator/business-level metadata
- `advertiser_profiles` stores advertiser/business-level metadata
- `sessions` stores login session state if session persistence is later moved fully into DB

### Catalog and classification

- categories
- genres
- grades
- languages
- titles
- title_genres
- title_languages

Purpose:

- `categories` stores top-level content categories such as Movies and Web Series
- `genres` stores the managed genre taxonomy
- `grades` stores certification/age-grade taxonomy
- `languages` stores the managed language taxonomy
- `titles` stores the main content record
- `title_genres` maps many genres to one title
- `title_languages` maps many languages to one title

### Media and asset storage

- title_posters
- title_music
- title_trailers
- title_content_files
- title_subtitle_tracks
- title_audio_tracks

Purpose:

- `title_posters` stores poster asset metadata
- `title_music` stores music asset metadata
- `title_trailers` stores teaser/trailer asset metadata
- `title_content_files` stores main playable content files
- `title_subtitle_tracks` stores subtitle track files
- `title_audio_tracks` stores alternate or selectable audio tracks

### Episodic expansion

- seasons
- episodes

Purpose:

- `seasons` groups episodes under a title where needed
- `episodes` stores episode-level metadata for Web Series and TV Shows

Phase 1 note:

- These can start as optional future tables if title-level media is enough for the first implementation
- But the schema should avoid blocking their introduction later

### Commerce and wallet

- wallets
- wallet_transactions
- reservations
- reservation_events

Purpose:

- `wallets` stores balances such as available stars, blocked stars, and disks
- `wallet_transactions` stores purchases, conversions, refunds, and deductions
- `reservations` stores current reservation state per user and title
- `reservation_events` stores reservation history such as block, cancel, commit, and release

### Campaigns and monetization

- ad_campaigns
- disk_reward_events
- title_promotions

Purpose:

- `ad_campaigns` stores advertiser campaigns
- `disk_reward_events` stores disk earning actions
- `title_promotions` stores title-linked promotional campaigns

### Moderation and platform operations

- publish_submissions
- admin_actions
- audit_logs

Purpose:

- `publish_submissions` stores creator publishing workflow requests
- `admin_actions` stores key admin decisions on titles, users, and promotions
- `audit_logs` stores important platform-level history for accountability and troubleshooting

## 4S. Suggested First Implementation Scope

To avoid overbuilding too early, the first DB implementation can be phased.

### Phase 1 core tables

- users
- creator_profiles
- categories
- genres
- grades
- languages
- titles
- title_genres
- title_languages
- title_posters
- title_music
- title_trailers
- title_content_files
- title_subtitle_tracks
- title_audio_tracks
- wallets
- wallet_transactions
- reservations
- publish_submissions

### Phase 2 likely additions

- advertiser_profiles
- ad_campaigns
- disk_reward_events
- seasons
- episodes
- reservation_events
- audit_logs

This phased model should let us move forward without losing the larger architecture.

## 4P. Suggested Episode / Series Direction

Because Web Series and TV Shows are core categories, the model should prepare for episodic content early.

Recommended direction:

- Use one main title as the parent show record
- Link seasons and episodes under that title

Possible future structure:

- title record for the show
- season record
- episode record
- episode media records

Phase 1 shortcut if needed:

- Start with title-level support
- Add optional season_number and episode_number in content media records
- Expand to separate season and episode tables later when required

## 4Q. Suggestions And Recommendations

### Strong recommendation 1: keep search metadata separate from playback tracks

Use:

- `genres`, `languages`, `grade`, `category` for search and discovery
- `audio tracks` and `subtitle tracks` for playback controls

This separation keeps the system easier to manage and less confusing later.

### Strong recommendation 2: use asset tables, not only folder paths

Even though folders are useful on storage, DB records should describe each actual asset.

Why:

- easier admin editing
- better auditability
- better asset activation/deactivation
- cleaner random poster selection

### Strong recommendation 3: prepare now for episodic content

Because Web Series and TV Shows are already primary categories, the media model should not assume every title is one single movie file forever.

### Strong recommendation 4: define status carefully

A simple status model later could be:

- draft
- submitted
- approved
- upcoming_live
- reserve_live
- released_live
- library_live
- cancelled
- archived

This will help admin workflows, creator workflows, and viewer visibility rules stay predictable.

## 4A. Genre Taxonomy

Current starter genre list:

- Fantasy
- Horror
- Sci-Fi
- Romance
- Thriller
- Drama
- Epic
- Action
- Heist

Additional recommended genres:

- Comedy
- Adventure
- Crime
- Mystery
- Family
- Animation
- Documentary
- Biography
- Historical
- War
- Sports
- Musical
- Suspense
- Supernatural

Notes:

- `Thriller` is the preferred spelling instead of `Triller`
- A title should support multiple genres instead of only one
- Genre rules may later be separated from mood, theme, and category
- Genre selections should later be usable in app search and filtering
- Genre definitions should be manageable from the admin panel

Admin expectations for genre management:

- Add new genres
- Edit existing genres
- Deactivate unused genres
- Control display order if needed
- Keep the searchable genre taxonomy clean and consistent

## 4B. Grade / Certification Taxonomy

Current starter grade list:

- PG
- 16+
- A

Additional recommended grades for future support:

- U
- U/A 7+
- U/A 13+
- U/A 16+
- 18+

Notes:

- Grade values should be manageable from the admin panel
- Grade values should later be usable in search, filtering, and parental-control logic
- Regional certification mapping may be needed later if the app expands across multiple countries
- Each title should have a selectable grade from the managed grade list
- Grade selections should later work as searchable and filterable metadata in the app

Admin expectations for grade management:

- Add new grades
- Edit display labels if needed
- Deactivate unused grades
- Control display order if needed
- Keep certification data consistent across all titles

## 4C. Language Taxonomy

Current starter language list:

- English
- Hindi
- Telugu
- Tamil
- Kannada
- Malayalam
- Marathi
- French
- Spanish

Additional recommended languages for future support:

- Bengali
- Punjabi
- Gujarati
- Japanese
- Korean
- German
- Arabic

Notes:

- Language values should be manageable from the admin panel
- A title should support multiple languages where applicable
- Language values should later be usable in search and filtering
- The system may later need to separate:
  - content language
  - audio language
  - subtitle language
- Regional language expansion should remain easy as the platform grows

Admin expectations for language management:

- Add new languages
- Edit existing languages
- Deactivate unused languages
- Control display order if needed
- Keep the searchable language taxonomy clean and consistent

## 5. Current Role Model

Current known roles:

- Super Admin
- Admin
- Viewers
- Creators
- Advertisers

Note:
The current backend still uses the internal role value `producer` in some places for compatibility, but the UI language is being moved to `Creator`.

## 5A. Role Responsibilities And Permissions

This section defines the current intended access boundaries for each role.
It can be expanded later if new roles are introduced.

### Super Admin

Purpose:

- Full platform control
- Final authority over configuration, access, moderation, and platform operations

Permissions:

- Manage all users and roles
- Create, edit, disable, or reactivate admin accounts
- Manage creators, viewers, and advertisers
- Access all admin panels and future system modules
- Override content status and library placement
- Approve or reject sensitive platform changes
- View platform-wide reports and audit data
- Manage security, policies, and high-level settings

Restrictions:

- Should be limited to a very small number of trusted accounts

### Admin

Purpose:

- Operate the platform on a day-to-day basis
- Moderate content, users, and publishing flow

Permissions:

- Manage viewers
- Manage creators
- Manage advertisers
- Review and moderate content submissions
- Manage categories
- Manage content categories
- Manage genres
- Manage grades
- Manage languages
- Manage library and content placement
- Feature sections and campaigns
- Review reservation-related operational data
- Archive or move content between platform sections

Restrictions:

- Should not manage Super Admin accounts
- Should not access highest-level platform security controls unless explicitly allowed later

### Viewers

Purpose:

- Discover content
- Show interest
- Reserve content
- Consume content through approved access

Permissions:

- Create and manage personal account
- Browse upcoming, released, and library content
- Watch posters, teasers, trailers, and supporting media
- Mark `Wish To Watch`
- Buy stars
- Earn disks
- Convert disks into stars
- Reserve content using stars
- Cancel reservations before the allowed cutoff
- Access purchased or released content when entitled
- View personal wallet balances and reservation history

Restrictions:

- No content publishing permissions
- No user-management permissions
- No platform moderation permissions

### Creators

Purpose:

- Upload and manage content projects
- Measure audience demand
- Decide app-release strategy

Permissions:

- Create and manage creator profile
- Upload upcoming projects
- Upload posters, teasers, trailers, and title details
- Set story, genres, languages, grade, and category
- Define star pricing per title
- Set tentative release dates
- Activate or deactivate `Reserve Now`
- Choose cancellation lock cutoff within platform rules
- Monitor wish interest and reservation demand
- Track expected revenue against target
- Confirm app release or cancel app release
- Manage project lifecycle subject to admin oversight

Restrictions:

- Should not directly manage users outside their own account/team scope
- Should not bypass admin moderation rules
- Should not access platform-wide financial or security controls unless explicitly allowed later

### Advertisers

Purpose:

- Support the rewards and promotional economy
- Drive disk earning campaigns and sponsored visibility

Permissions:

- Create and manage advertiser profile
- Run approved ad campaigns
- Sponsor disk-based reward opportunities
- Associate promotions with content, categories, or campaigns
- View advertiser campaign performance data

Restrictions:

- No direct control over content publishing
- No user-management permissions
- No admin moderation permissions
- Reward or ad activity should remain subject to admin approval and platform policy

## 6. Core User Features

### Viewer

- Browse content by stage
- View posters and details
- View teasers and trailers
- View brief story, genre, language, grade, and category
- Mark `Wish To Watch`
- Use `Reserve Now`
- Buy stars through payments
- Collect disks through ads, promotions, or product purchases
- Convert disks into stars
- Access rewards in the future
- Access personal collection and booked titles in later phases

### Creator

- Upload title information
- Upload posters, teasers, and trailers
- Add preview information
- Add brief story
- Add language, grade, and category
- Add budget and expected revenue
- Set a tentative release date
- Activate or deactivate `Reserve Now`
- Submit content into the publishing flow
- Preview before publishing
- Decide later whether to release inside the app
- Cancel app release if targets are not met
- Submit all new or updated content into the approval flow instead of publishing directly
- Wait for Super Admin approval before any content becomes viewer-visible

### Admin

- Manage users
- Manage categories
- Manage library
- Review submission queue
- Move titles between sections
- Feature sections for viewers
- Boost campaigns and rewards
- Archive titles from public catalog
- Review creator and admin-submitted content before sending it for final approval
- Do not publish content directly to viewers without Super Admin approval

### Super Admin Approval Rule

This is a standing product requirement for all future coding work:

- Any new content created from Creator or Admin panels must require Super Admin approval before publishing
- Any updates to existing content from Creator or Admin panels must require Super Admin approval before publishing
- Every title-level asset must follow this rule, including:
- Posters and images
- Teasers and trailers
- Main content/video files
- Other related media or metadata updates
- Viewer visibility should only happen after review and final Super Admin approval

Implementation direction from this point onward:

- Treat Creator and Admin actions as submission or review steps
- Treat Super Admin as the final publishing authority
- Keep approval status in mind for every future content workflow, upload flow, and publish action

## 7. Admin Panel Direction

The admin panel is intended to be separate from the public website experience.

Current admin navigation direction:

- Manage Users
- Manage Categories
- Manage Library

Suggested future admin modules:

- Manage Banners
- Manage Rewards
- Manage Advertisers
- Manage Creator Accounts
- Reports
- Security / Audit Logs

## 8. Content Lifecycle

Current intended flow:

1. Creator uploads an upcoming project with posters, teasers, trailers, story, genre, language, grade, and category.
2. The content appears in Upcoming for discovery and audience interest collection.
3. Viewers watch the promotional material and mark `Wish To Watch` if interested.
4. Creator studies wish counts, trailer engagement, and early audience response.
5. Creator may activate `Reserve Now` with a tentative release timeline.
6. Viewers block stars to reserve access before release.
7. The platform tracks whether expected revenue is reaching the creator's target.
8. If the target is reached, the creator can confirm the release date in the app.
9. If the creator decides not to release in the app, blocked stars are returned to viewers.
10. Once released, the title moves into New Released.
11. After its active release window, it moves into Old Movies / Library.

This flow should later be generalized beyond films so that non-movie content also fits naturally.

## 8A. Pricing Model Per Content

Each content item can have its own reservation price in stars.

Examples:

- 1 star
- 2 stars
- 3 stars

This means the creator can decide a different star price per title depending on:

- Content type
- Budget
- Audience demand
- Release strategy
- Expected revenue target

This pricing should be configurable at the content level.

## 8B. Star Economy

Stars are the main reservation-value unit used inside the platform.

Current base pricing rule:

- 1 star = Rs 100
- Taxes such as GST are excluded from the base star value
- Any other applicable taxes are also excluded from the base star value

Payment rule:

- Users pay based on the number of stars needed by the selected title
- Example: if a title costs 3 stars, the base content value is Rs 300 before GST and other taxes

Currency handling rule:

- If payment is made in another currency, it should first be converted from the rupee base value
- The app should show the equivalent star price in that currency before taxes
- Taxes should be shown separately

Wallet issue rule:

- After payment is successfully received, the corresponding number of stars should be issued to the user
- These stars can then be blocked or used for reservations

## 8C. Disk Economy

Disks are a secondary earning unit for viewers.

Users can earn disks through activities such as:

- Viewing advertisements
- Purchasing products
- Promotional campaigns
- Other future reward activities

Conversion rule:

- 1000 disks = 1 star

This means users can:

- Accumulate disks over time
- Convert disks into stars
- Use those stars for content reservations

## 8D. Reservation Funding Sources

A user may be able to reserve content using:

- Purchased stars
- Converted stars from disks
- A combination of both, if supported later

This should later be modeled in the wallet system so that reservations clearly show:

- stars available
- stars blocked
- disks available
- converted stars history
- refunded stars when a release is cancelled

## 8E. Reservation Blocking Logic

Current intended reservation rule:

- If a user has 10 stars and reserves a title costing 3 stars, then 3 stars become blocked
- The user can then spend only the remaining 7 available stars on other titles or actions

This means the wallet should distinguish between:

- total stars
- available stars
- blocked stars

Example:

- Total stars: 10
- Blocked stars: 3
- Available stars: 7

The blocked stars are not immediately treated as final creator revenue.
They remain reserved inside the user's wallet until the title reaches its final release preparation stage.

## 8F. Cancellation Window Logic

Users should be allowed to cancel a reservation before a creator-defined lock cutoff.

Current intended direction:

- Each title can have its own cancellation lock period
- Example: reservation cancellation may be allowed until 1 week before the release date
- This lock period will be decided by the creator or movie maker for that title
- The platform should enforce a safe creator-configurable range for this cutoff

Current platform rule:

- Minimum lock cutoff: 3 days before release
- Maximum lock cutoff: 14 days before release

This means:

- Creators cannot allow cancellation later than 3 days before release
- Creators cannot lock reservations earlier than 14 days before release
- Creators may choose any cutoff within that allowed range

If the user cancels before the lock cutoff:

- the blocked stars are released back to available stars
- the user regains full spending access to those stars

If the user tries to cancel after the lock cutoff:

- cancellation may no longer be allowed
- the blocked stars stay committed for final release fulfillment

## 8G. Final Deduction Timing

Current intended deduction rule:

- Stars are blocked at the time of reservation
- Stars are not finally deducted immediately
- Final deduction happens just before the release date, when the title download is prepared or pushed to the user before release

This means the lifecycle is:

1. User reserves title
2. Required stars are blocked
3. User may cancel before the lock cutoff
4. After the cutoff, reservation becomes committed
5. Just before release delivery, blocked stars are converted into final deducted stars
6. The content download or access package is then pushed to the user before release

This approach helps:

- users keep clarity on what is still spendable
- creators see committed demand before release
- the system handle controlled cancellation windows cleanly
- the app align payment commitment with delivery timing

## 9. Security and Playback Direction

Several playback and protection decisions were discussed already.

Current understanding:

- Browser playback cannot fully prevent determined users from capturing decrypted media once playback happens on the client.
- Even if a file is encrypted, playback in a browser eventually exposes decrypted media to client-side playback paths.
- Browser memory or GPU memory cannot be fully protected from advanced user-side capture attempts.
- Server validation before playback is possible, but once content is decrypted client-side, absolute prevention is not guaranteed.

Current practical direction:

- Use authentication and controlled access
- Restrict admin APIs with session-based auth
- Treat browser playback as controlled access, not perfect anti-rip security
- Consider stronger restrictions later in a dedicated desktop app if tighter playback control is required

Product-level anti-piracy goal:

- Make piracy significantly harder and less attractive
- Give creators enough confidence to consider app-first or app-plus-theatre release
- Build a legal and technical system that is stronger than typical open streaming flows, while recognizing that no client playback model can guarantee perfect prevention

## 10. Current Technical Direction

Current stack direction:

- Backend: Python
- Frontend: JavaScript
- Database: PostgreSQL

Platform priority direction:

- Primary target: Mobile apps
- Primary mobile platforms: Android and iPhone
- Secondary target: Website

This means the product should be planned mobile-first in:

- user flows
- wallet usage
- reservation UX
- notifications
- content delivery
- playback and access control

The website should still exist, but mainly as:

- a secondary consumer surface
- a support and discovery surface
- a companion access point where needed

Current backend capabilities already started:

- FastAPI backend
- PostgreSQL-backed persistence
- Seeded users and movie data
- Session-based admin authentication
- Admin summary and management APIs
- Creator publishing queue flow

## 11. Current Naming Direction

Current working product name:

- Cine Vault

Design direction already chosen:

- Dark mode oriented UI
- Premium entertainment feel
- Public viewer experience separate from admin workspace
- Mobile-first product thinking, with web as a secondary surface

## 12. Open Product Questions

These need clearer decisions later:

- Should categories later become more generic than only movie-based stage names?
- Should a title ever belong to more than one top-level category, or only one primary category?
- Should `Released` later support both `Owned` and `Subscription Included` if a subscription model is introduced?
- Should `Library` later support additional monetization types beyond `Free with Ads` and `Pay Now`?
- How should web series and TV shows be represented inside the same library model?
- Should genres be grouped under parent families later, for example `Crime` and `Heist` under a broader discovery structure?
- Should language filters later distinguish original language, dubbed audio, and subtitle availability?
- Should captions be searchable metadata, or only display metadata?
- Should titles later support both teaser and trailer together instead of only one required media asset?
- Should posters be tagged beyond orientation, for example hero poster, detail poster, campaign poster, or thumbnail poster?
- Should alternate audio be stored as separate files, muxed tracks, or adaptive-stream track variants?
- Should subtitles be stored as WebVTT, SRT, or another format for the main app players?
- Should `Reserve Now` represent payment, token reservation, or booking intent first?
- How exactly should stars be earned, purchased, blocked, and refunded?
- Should stars expire, or remain permanently in the user wallet?
- Should disks expire after a certain time?
- Can disks be partially converted, or only in blocks of 1000?
- Can a user combine cash-purchased stars and disk-converted stars in the same reservation?
- What should happen if taxes vary by country while the base star value remains tied to rupees?
- Should the creator-defined cancellation cutoff be mandatory, or should the platform enforce a minimum and maximum window?
- What exact event should trigger the final deduction: pre-download push, decryption enablement, or release unlock?
- What business rules decide when a creator may activate `Reserve Now`?
- What creator-side threshold defines "expected revenue target reached"?
- Can a title release both in theatres and in the app on the same date, or will this vary title by title?
- How will rewards be earned, stored, and redeemed?
- How should advertisers and reward publishers appear in the role model?
- What responsibilities and permissions should advertisers have inside the platform?
- What level of creator self-service should be allowed versus admin-only control?

## 13. Immediate Priorities

Current short-term priorities:

- Keep refining the product brief
- Build the Phase 1 admin workflow
- Improve the Creator-side workflow
- Expand catalog and content management structure
- Decide how non-movie content types fit the model
- Continue turning placeholder flows into real backend-driven features
- Keep future architecture aligned with Android-first and iPhone-first app delivery
- Finish the hosted stable delivery flow before starting `M-P2P`
- After Railway deployment and short-title testing, begin the `M-P2P` prototype track

## 14. Change Log Notes

Use this section for quick future updates.

- UI wording changed from `Producer` to `Creator`
- Admin panel separated from the public website layout
- Super Admin default login added
- Admin APIs protected using session-based sign-in
- Added star-based pricing and disk-to-star reward economy notes
- Added blocked-star reservation, creator-defined cancellation window, and final deduction timing notes
- Added platform-enforced creator cancellation cutoff range of 3 to 14 days before release
- Marked Android and iPhone apps as primary targets, with website as secondary
