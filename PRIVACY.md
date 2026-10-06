# Privacy Policy: How Come YouTube Automation

**Last updated:** 6 October 2026

## 1. About this app

"How Come YouTube Automation" (the "App") is a small personal automation tool. It is operated by
**[YOUR NAME OR BUSINESS NAME]** ("we", "us"). It is used only by its operator, to upload videos
that the operator has made to YouTube channels that the operator owns.

The App is not offered to the public. It has no accounts for other people, no sign-up and no
website for visitors. This policy explains what information the App handles and why.

## 2. YouTube API Services

The App uses **YouTube API Services**.

By using the App you agree to be bound by the
[YouTube Terms of Service](https://www.youtube.com/t/terms). Information obtained through the
YouTube API Services is also subject to the
[Google Privacy Policy](http://www.google.com/policies/privacy).

## 3. Information the App accesses

The App asks the channel owner for permission to use two Google API scopes:

| Permission (scope) | What the App uses it for |
|---|---|
| `https://www.googleapis.com/auth/youtube.upload` | Uploading videos, and setting their title, description, tags, visibility and thumbnail, on the owner's channel. |
| `https://www.googleapis.com/auth/youtube.readonly` | Reading the basic details of the owner's channel (its ID and name) to confirm that an upload is going to the intended channel and not to a different one. |

The Google user data the App handles is therefore limited to:

- the OAuth tokens that Google issues after the owner approves access, and
- the ID and name of the owner's YouTube channel.

The App does **not** access anyone else's information. It does not read subscribers, comments,
analytics, watch history, private videos, contacts, email or any other Google account data.

## 4. How the information is used

The information is used only to provide the App's features described in section 1: confirming the
channel, uploading videos and thumbnails, and setting their details.

We do not use it for advertising, marketing, profiling, analytics or tracking. We do not sell it.
No information obtained from Google APIs is used to develop, improve or train artificial
intelligence or machine-learning models, and none is sent to any AI service.

## 5. Storage, retention and security

- **Tokens.** The OAuth tokens are stored as encrypted secrets in the settings of the operator's
  private GitHub repository, and in a local configuration file on the operator's own computer that
  is never uploaded. They are kept until access is revoked, they expire, or the operator deletes
  them.
- **Channel details.** The channel ID is kept as a setting so that uploads can be checked against it.
- **Logs.** The automation's run logs, visible only to the operator, show the channel name and ID and
  the ID of each uploaded video. GitHub deletes these logs automatically after its retention period.
- **Nothing else is stored.** The App has no database and keeps no other Google user data.
- **Security.** The repository is private, secrets are encrypted by GitHub, and only the
  operator's automation can use them.

## 6. Sharing

We do not sell, rent or share information received from Google APIs with anyone, except where the law
requires it.

To make its videos, the App also uses other services: an AI service that writes story text, a stock
video service that supplies footage, and a speech service that reads the story aloud. These services
receive only story text and search words. They never receive Google user data, OAuth tokens, or
anything about the channel's viewers. The only data the App sends to Google is the videos and
thumbnails that the operator chooses to upload.

## 7. Google API Services User Data Policy: Limited Use

How Come YouTube Automation's use and transfer to any other app of information received from Google
APIs will adhere to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

In particular, information received from Google APIs is used only to provide the App's visible
features, is not transferred to others except as necessary to provide those features or to comply with
the law, is not used for advertising, and is not read by any person other than the operator of the
App, whose own channel it concerns.

## 8. Your choices: revoking access and deleting data

You can withdraw the App's access at any time:

1. Open the Google account permissions page at
   <https://security.google.com/settings/security/permissions>.
2. Choose "How Come YouTube Automation" and select **Remove access**.

You can also delete the stored tokens yourself by removing the GitHub secrets and the local
configuration file.

Once access is revoked, the App can no longer use YouTube API Services. We delete any stored tokens
and channel details as soon as possible and in any case within 30 days.

Videos that were already uploaded stay on YouTube and are managed by the channel owner in YouTube
Studio. To ask a question or request deletion, contact us (section 11).

## 9. Children

The App is not directed at children and does not knowingly collect personal information from anyone.

## 10. Changes to this policy

If the App changes how it uses information, we will update this policy and its date before the change
takes effect, and will ask for fresh permission where Google's policies require it.

## 11. Contact

**[YOUR NAME OR BUSINESS NAME]**
Email: **[YOUR CONTACT EMAIL]**
