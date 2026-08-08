REGISTRATION_DESCRIPTION = """

**Description**: Registriert einen neuen Benutzer im System.

### Request Body

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "confirmed_password": "securepassword"
}
```

### Success Response

Nach erfolgreicher Registrierung wird eine Aktivierungs-E-Mail versendet. 
Der Response inkl. dem Token hat keine Verwendung im FrontEnd, da wir hier 
mit HTTP-ONLY-COOKIES arbeiten. Dieser ist zur Demonstration und Information für Dich.

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com"
  },
  "token": "activation_token"
}
```

### Status Codes

-   **201**: Benutzer erfolgreich erstellt.
-   **400**: Ungültige Daten.
-   **500**: Interner Serverfehler.

### Rate Limits

- No limit.

### Permissions required: 

- No Permissions required

### Extra Information:

-   Konto bleibt inaktiv bis Aktivierung via E-Mail.

"""
