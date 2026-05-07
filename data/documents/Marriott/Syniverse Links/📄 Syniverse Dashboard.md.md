# Syniverse Messaging Gateway – Dashboard

A Dataview-powered overview of all Syniverse reference materials.

  

---

  

## 🔐 Access & Security

```dataview

TABLE name, url

FROM "Syniverse Links"

WHERE type = "syniverse-link" AND category = "Access"

SORT name ASC
````

## API Documentation

```dataview

TABLE name, url

FROM "Syniverse Links"

WHERE type = "syniverse-link" AND category = "API"

SORT name ASC
````

## Webhook

```dataview

TABLE name, url

FROM "Syniverse Links"

WHERE type = "syniverse-link" AND category = "Webhook"

SORT name ASC
