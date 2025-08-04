# Notifications

This package centralizes notification logic for the project.

## Service function

`dispatch_notification(user, message, **context)` is the single entry point
for creating notifications. By using a common helper we can later switch or
augment backends without touching callers.

## Extension points

The service currently only logs messages. Future contributions may:

- **Django Channels** – emit events so connected clients receive real-time updates.
- **Push/Email providers** – forward notifications to external push or email
  services.

Add logic for these providers inside `dispatch_notification` where TODO markers
are placed.
