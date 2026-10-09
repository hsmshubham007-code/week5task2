# Chinook Database Schema

## Overview

Week 5 Task 2 uses the Chinook SQLite sample database (`data/chinook.db`) for a read-only text-to-SQL agent.

**Verified database size:** 11 application tables and 15,607 total rows.

## Tables

| Table         | Purpose                               | Important columns                                         |
| ------------- | ------------------------------------- | --------------------------------------------------------- |
| Artist        | Music artists                         | ArtistId, Name                                            |
| Album         | Albums and artists                    | AlbumId, Title, ArtistId                                  |
| Track         | Individual tracks                     | TrackId, Name, AlbumId, GenreId, MediaTypeId, UnitPrice   |
| Genre         | Music categories                      | GenreId, Name                                             |
| MediaType     | Audio formats                         | MediaTypeId, Name                                         |
| Playlist      | Playlists                             | PlaylistId, Name                                          |
| PlaylistTrack | Playlist membership                   | PlaylistId, TrackId                                       |
| Customer      | Customers and contact details         | CustomerId, FirstName, LastName, Country, SupportRepId    |
| Employee      | Employees and support representatives | EmployeeId, FirstName, LastName, ReportsTo                |
| Invoice       | Customer purchases                    | InvoiceId, CustomerId, InvoiceDate, Total, BillingCountry |
| InvoiceLine   | Individual invoice items              | InvoiceLineId, InvoiceId, TrackId, UnitPrice, Quantity    |

## Relationships

* Album.ArtistId → Artist.ArtistId
* Track.AlbumId → Album.AlbumId
* Track.GenreId → Genre.GenreId
* Track.MediaTypeId → MediaType.MediaTypeId
* PlaylistTrack.PlaylistId → Playlist.PlaylistId
* PlaylistTrack.TrackId → Track.TrackId
* Invoice.CustomerId → Customer.CustomerId
* InvoiceLine.InvoiceId → Invoice.InvoiceId
* InvoiceLine.TrackId → Track.TrackId
* Customer.SupportRepId → Employee.EmployeeId
* Employee.ReportsTo → Employee.EmployeeId

## Common join paths

* Customer → Invoice → InvoiceLine for customer purchases and sales.
* InvoiceLine → Track → Album → Artist for sales by artist or album.
* Track → Genre for genre analysis.
* Track → MediaType for format analysis.
* Customer → Employee for support representative information.
* Playlist → PlaylistTrack → Track for playlist contents.

## Safety boundary

The agent must only execute permitted read-only queries. SQL must be validated before every execution. The database connection must enforce read-only access independently of the language model.

## Known limitations

The database does not provide every business metric. For example, it does not contain employee performance ratings, inventory stock levels, marketing campaign expenditure, or refund records. The agent must acknowledge missing data instead of inventing answers.

## Verification

The local database was inspected with Python's SQLite library. The `Customer`–`Invoice` join was executed successfully and returned five sample rows. The row counts and schema should be rechecked by the project verification scripts when running in another environment.
