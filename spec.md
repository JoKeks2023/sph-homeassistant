# Schulportal Hessen for Home Assistant

**Project Specification**

| Property | Value |
|---|---|
| Project name | Schulportal Hessen |
| Platform | Home Assistant |
| Project type | Custom Integration |
| License | Open Source |
| Primary language | Python |
| Initial target | Functional MVP |
| Installation | HACS / Home Assistant Marketplace compatible |

## 1. Product Vision

Schulportal Hessen for Home Assistant brings school-related information from the Hessian School Portal (Schulportal Hessen) into Home Assistant.

The integration should make everyday school information accessible through Home Assistant entities, calendars and automations.

The goal is to provide a convenient, reliable and privacy-friendly way to access school information without having to open the Schulportal website or app.

The integration is intended for personal use as well as potential public distribution as an open-source project.

## 2. Scope

The integration should support the following information categories:

### 2.1 Timetable (Stundenplan)

Display the user's regular timetable.

Requirements:
- Retrieve timetable information.
- Display upcoming lessons.
- Provide information about lesson times, subjects, rooms and teachers where available.
- Make timetable information accessible to Home Assistant.
- Account for changes to the regular timetable.

### 2.2 Substitution Schedule (Vertretungsplan)

Display current substitution and schedule changes.

Requirements:
- Retrieve current substitution information.
- Identify affected lessons.
- Display changes to rooms, teachers and subjects where available.
- Distinguish regular timetable information from substitution information.
- Update when new substitution information becomes available.

### 2.3 Homework (Hausaufgaben)

Make homework information accessible.

Requirements:
- Retrieve available homework entries.
- Display descriptions and relevant dates.
- Provide due dates where available.
- Allow Home Assistant automations to react to new or upcoming homework.

### 2.4 Calendar (Kalender)

Provide access to school-related calendar events.

Requirements:
- Retrieve available calendar events.
- Include dates, times, titles and descriptions where available.
- Make events accessible through a Home Assistant calendar entity.
- Support upcoming and future events.

### 2.5 Messages (Nachrichten)

Provide access to messages from the Schulportal.

Requirements:
- Retrieve available messages.
- Display sender, subject, date and relevant content where accessible.
- Make new messages detectable.
- Support automations based on incoming messages.

The integration must not send messages or perform actions on behalf of the user.

### 2.6 Exams and Tests (Klausuren und Tests)

Provide access to upcoming exams and tests.

Requirements:
- Retrieve exam and test information where available.
- Display subject, date, time and additional information where provided.
- Make upcoming exams accessible to Home Assistant automations.
- Distinguish exams from ordinary calendar events where possible.

## 3. Home Assistant Experience

The integration should feel like a native Home Assistant integration.

Requirements:

- Integration setup through the Home Assistant UI.
- No manual YAML configuration required.
- Entities should have meaningful names and unique IDs.
- Entities should expose useful attributes.
- Entities should be usable in dashboards, automations and scripts.
- Appropriate device and entity metadata.
- German and English translations.

### Entity types

The integration should use appropriate Home Assistant entity types.

Expected possibilities include:

- Sensors for current and upcoming school information.
- Calendar entities for timetable entries, exams and school events.
- Additional entity types only where they provide meaningful functionality.

The exact entity model is an implementation decision.

## 4. Configuration and Authentication

Users must be able to connect their Schulportal Hessen account through the Home Assistant UI.

Requirements:

- Username and password configuration.
- School identification where required.
- Validation of credentials during setup.
- Secure storage of authentication information.
- Proper handling of expired sessions and authentication failures.
- Clear error messages for users.

The integration must never expose passwords, authentication tokens or other sensitive information through logs or entity attributes.

## 5. Data Synchronization

The integration must retrieve information automatically and keep Home Assistant entities up to date.

Requirements:

- Automatic periodic updates.
- Efficient retrieval without unnecessary requests.
- Appropriate handling of temporary network failures.
- Recovery after Home Assistant restarts.
- Handling of unavailable or incomplete data.
- No misleading or fabricated information.

Update frequency should be appropriate for the individual data categories and the capabilities of the Schulportal.

## 6. Architecture and Dependencies

The integration must run directly within Home Assistant.

Constraints:

- No separate backend service.
- No external database.
- No additional Docker container.
- No mandatory third-party cloud service.
- No separate mobile application.
- No write operations to the Schulportal.

The choice of API client, Python libraries, internal architecture and data models is deliberately left open to the implementation phase.

Existing open-source Schulportal projects may be reused where technically suitable and compatible with the project's license.

## 7. Privacy and Security

Privacy is a core requirement.

- Credentials must be stored securely.
- No school account information may be transmitted to unrelated external services.
- No telemetry or analytics without explicit user consent.
- No sensitive information in diagnostic logs.
- Read-only access to the Schulportal.
- Dependencies must be reviewed for licensing and security implications.

## 8. Reliability and Error Handling

The integration should remain stable even if the Schulportal is temporarily unavailable.

It should:

- Distinguish between missing data and connection failures.
- Handle authentication errors gracefully.
- Avoid unnecessary repeated login attempts.
- Preserve the last successfully retrieved data where appropriate.
- Clearly indicate unavailable entities when data cannot be refreshed.

## 9. Distribution and Open Source

The project should be published publicly on GitHub.

Requirements:

- Open-source license.
- Clear README.
- Installation and configuration documentation.
- Versioning and release notes.
- Repository structure suitable for HACS distribution.
- Compatibility with applicable Home Assistant integration and marketplace requirements.
- Contributions should be possible through issues and pull requests.

## 10. MVP and Acceptance Criteria

The first release should prioritize a working integration over completeness.

The MVP is considered successful when:

1. Users can install the integration.
2. Users can configure their Schulportal account through the UI.
3. Authentication works reliably.
4. At least the core school information can be retrieved.
5. Retrieved information appears as usable Home Assistant entities.
6. Data updates automatically.
7. Authentication and connection errors are handled properly.
8. The integration works without an additional service or container.

All six information categories listed in Section 2 are intended project goals. Features that are not technically accessible through the available Schulportal interfaces must be documented rather than simulated.

## 11. Out of Scope

The following are explicitly not part of this project:

- Sending messages.
- Editing homework or calendar entries.
- Changing timetable information.
- Managing school accounts.
- Replacing the official Schulportal website or mobile application.
- Building a standalone mobile or web application.
- Providing a general-purpose Schulportal API for other applications.

## 12. Product Principle

The project should be small, focused and maintainable.

The priority is a reliable Home Assistant integration that solves a real everyday problem. Avoid unnecessary complexity and prioritize practical functionality, a good user experience and long-term maintainability.
