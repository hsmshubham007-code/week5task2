
QUESTIONS = [
    {
        "id": "Q001",
        "question": "How many customers are in the database?",
        "sql": "SELECT COUNT(*) AS customer_count FROM Customer",
    },
    {
        "id": "Q002",
        "question": "How many employees are there?",
        "sql": "SELECT COUNT(*) AS employee_count FROM Employee",
    },
    {
        "id": "Q003",
        "question": "How many music tracks are available?",
        "sql": "SELECT COUNT(*) AS track_count FROM Track",
    },
    {
        "id": "Q004",
        "question": "How many artists are represented?",
        "sql": "SELECT COUNT(*) AS artist_count FROM Artist",
    },
    {
        "id": "Q005",
        "question": "How many albums are in the catalog?",
        "sql": "SELECT COUNT(*) AS album_count FROM Album",
    },
    {
        "id": "Q006",
        "question": "How many invoices have been recorded?",
        "sql": "SELECT COUNT(*) AS invoice_count FROM Invoice",
    },
    {
        "id": "Q007",
        "question": "Which five countries have the most customers?",
        "sql": """
            SELECT Country, COUNT(*) AS customers
            FROM Customer
            GROUP BY Country
            ORDER BY customers DESC, Country
            LIMIT 5
        """,
    },
    {
        "id": "Q008",
        "question": "How many customers live in Canada?",
        "sql": """
            SELECT COUNT(*) AS customers
            FROM Customer
            WHERE Country = 'Canada'
        """,
    },
    {
        "id": "Q009",
        "question": "Show ten customers and their assigned support representatives.",
        "sql": """
            SELECT c.FirstName, c.LastName,
                   e.FirstName AS rep_first_name,
                   e.LastName AS rep_last_name
            FROM Customer c
            LEFT JOIN Employee e ON c.SupportRepId = e.EmployeeId
            ORDER BY c.CustomerId
            LIMIT 10
        """,
    },
    {
        "id": "Q010",
        "question": "Which five customers have the most invoices?",
        "sql": """
            SELECT c.CustomerId, c.FirstName, c.LastName,
                   COUNT(i.InvoiceId) AS invoice_count
            FROM Customer c
            JOIN Invoice i ON c.CustomerId = i.CustomerId
            GROUP BY c.CustomerId, c.FirstName, c.LastName
            ORDER BY invoice_count DESC, c.CustomerId
            LIMIT 5
        """,
    },
    {
        "id": "Q011",
        "question": "Which five customers have spent the most money?",
        "sql": """
            SELECT c.CustomerId, c.FirstName, c.LastName,
                   ROUND(SUM(i.Total), 2) AS total_spent
            FROM Customer c
            JOIN Invoice i ON c.CustomerId = i.CustomerId
            GROUP BY c.CustomerId, c.FirstName, c.LastName
            ORDER BY total_spent DESC, c.CustomerId
            LIMIT 5
        """,
    },
    {
        "id": "Q012",
        "question": "Which five billing countries generate the most revenue?",
        "sql": """
            SELECT BillingCountry, ROUND(SUM(Total), 2) AS revenue
            FROM Invoice
            GROUP BY BillingCountry
            ORDER BY revenue DESC, BillingCountry
            LIMIT 5
        """,
    },
    {
        "id": "Q013",
        "question": "What is the total revenue from all invoices?",
        "sql": "SELECT ROUND(SUM(Total), 2) AS total_revenue FROM Invoice",
    },
    {
        "id": "Q014",
        "question": "What is the average invoice amount?",
        "sql": "SELECT ROUND(AVG(Total), 2) AS average_invoice FROM Invoice",
    },
    {
        "id": "Q015",
        "question": "What is the monthly revenue, ordered from earliest to latest month?",
        "sql": """
            SELECT strftime('%Y-%m', InvoiceDate) AS month,
                   ROUND(SUM(Total), 2) AS revenue
            FROM Invoice
            GROUP BY month
            ORDER BY month
        """,
    },
    {
        "id": "Q016",
        "question": "Which five genres contain the most tracks?",
        "sql": """
            SELECT g.Name AS genre, COUNT(t.TrackId) AS track_count
            FROM Genre g
            JOIN Track t ON g.GenreId = t.GenreId
            GROUP BY g.GenreId, g.Name
            ORDER BY track_count DESC, genre
            LIMIT 5
        """,
    },
    {
        "id": "Q017",
        "question": "Which five albums have the most tracks?",
        "sql": """
            SELECT a.Title, COUNT(t.TrackId) AS track_count
            FROM Album a
            JOIN Track t ON a.AlbumId = t.AlbumId
            GROUP BY a.AlbumId, a.Title
            ORDER BY track_count DESC, a.Title
            LIMIT 5
        """,
    },
    {
        "id": "Q018",
        "question": "Which five artists have released the most albums?",
        "sql": """
            SELECT ar.Name, COUNT(a.AlbumId) AS album_count
            FROM Artist ar
            JOIN Album a ON ar.ArtistId = a.ArtistId
            GROUP BY ar.ArtistId, ar.Name
            ORDER BY album_count DESC, ar.Name
            LIMIT 5
        """,
    },
    {
        "id": "Q019",
        "question": "Which five playlists contain the most tracks?",
        "sql": """
            SELECT p.Name, COUNT(pt.TrackId) AS track_count
            FROM Playlist p
            JOIN PlaylistTrack pt ON p.PlaylistId = pt.PlaylistId
            GROUP BY p.PlaylistId, p.Name
            ORDER BY track_count DESC, p.Name
            LIMIT 5
        """,
    },
    {
        "id": "Q020",
        "question": "How many tracks are there for each media type?",
        "sql": """
            SELECT m.Name AS media_type, COUNT(t.TrackId) AS track_count
            FROM MediaType m
            LEFT JOIN Track t ON m.MediaTypeId = t.MediaTypeId
            GROUP BY m.MediaTypeId, m.Name
            ORDER BY track_count DESC, media_type
        """,
    },
    {
        "id": "Q021",
        "question": "Show the five longest tracks and their lengths in minutes.",
        "sql": """
            SELECT Name, ROUND(Milliseconds / 60000.0, 2) AS minutes
            FROM Track
            ORDER BY Milliseconds DESC, Name
            LIMIT 5
        """,
    },
    {
        "id": "Q022",
        "question": "Which five tracks have the highest unit prices?",
        "sql": """
            SELECT Name, UnitPrice
            FROM Track
            ORDER BY UnitPrice DESC, Name
            LIMIT 5
        """,
    },
    {
        "id": "Q023",
        "question": "What is the average track length in minutes for each genre?",
        "sql": """
            SELECT g.Name AS genre,
                   ROUND(AVG(t.Milliseconds) / 60000.0, 2) AS avg_minutes
            FROM Genre g
            JOIN Track t ON g.GenreId = t.GenreId
            GROUP BY g.GenreId, g.Name
            ORDER BY avg_minutes DESC, genre
        """,
    },
    {
        "id": "Q024",
        "question": "Which five genres generate the most sales revenue?",
        "sql": """
            SELECT g.Name AS genre,
                   ROUND(SUM(il.UnitPrice * il.Quantity), 2) AS revenue
            FROM Genre g
            JOIN Track t ON g.GenreId = t.GenreId
            JOIN InvoiceLine il ON t.TrackId = il.TrackId
            GROUP BY g.GenreId, g.Name
            ORDER BY revenue DESC, genre
            LIMIT 5
        """,
    },
    {
        "id": "Q025",
        "question": "Which five billing cities have the highest revenue?",
        "sql": """
            SELECT BillingCity, ROUND(SUM(Total), 2) AS revenue
            FROM Invoice
            GROUP BY BillingCity
            ORDER BY revenue DESC, BillingCity
            LIMIT 5
        """,
    },
    {
        "id": "Q026",
        "question": "Which customers have never made a purchase?",
        "sql": """
            SELECT c.CustomerId, c.FirstName, c.LastName
            FROM Customer c
            LEFT JOIN Invoice i ON c.CustomerId = i.CustomerId
            WHERE i.InvoiceId IS NULL
            ORDER BY c.CustomerId
        """,
    },
    {
        "id": "Q027",
        "question": "Which five invoices contain the most line items?",
        "sql": """
            SELECT i.InvoiceId, COUNT(il.InvoiceLineId) AS line_count
            FROM Invoice i
            JOIN InvoiceLine il ON i.InvoiceId = il.InvoiceId
            GROUP BY i.InvoiceId
            ORDER BY line_count DESC, i.InvoiceId
            LIMIT 5
        """,
    },
    {
        "id": "Q028",
        "question": "How much invoice revenue is associated with each support representative?",
        "sql": """
            SELECT e.EmployeeId, e.FirstName, e.LastName,
                   ROUND(SUM(i.Total), 2) AS revenue
            FROM Employee e
            JOIN Customer c ON e.EmployeeId = c.SupportRepId
            JOIN Invoice i ON c.CustomerId = i.CustomerId
            GROUP BY e.EmployeeId, e.FirstName, e.LastName
            ORDER BY revenue DESC, e.EmployeeId
        """,
    },
    {
        "id": "Q029",
        "question": "Show ten albums with their artist names and track counts.",
        "sql": """
            SELECT a.Title, ar.Name AS artist,
                   COUNT(t.TrackId) AS track_count
            FROM Album a
            JOIN Artist ar ON a.ArtistId = ar.ArtistId
            LEFT JOIN Track t ON a.AlbumId = t.AlbumId
            GROUP BY a.AlbumId, a.Title, ar.Name
            ORDER BY a.AlbumId
            LIMIT 10
        """,
    },
    {
        "id": "Q030",
        "question": "Which five countries have the highest average invoice amount?",
        "sql": """
            SELECT BillingCountry,
                   ROUND(AVG(Total), 2) AS average_invoice
            FROM Invoice
            GROUP BY BillingCountry
            ORDER BY average_invoice DESC, BillingCountry
            LIMIT 5
        """,
    },
]

UNANSWERABLE_QUESTIONS = [
    {
        "id": "U001",
        "question": "Which employee has the highest performance rating?",
        "reason": "The database has no employee performance ratings.",
    },
    {
        "id": "U002",
        "question": "How many physical units of each product are currently in stock?",
        "reason": "The database has no inventory stock quantities.",
    },
    {
        "id": "U003",
        "question": "How much money did we spend on marketing campaigns last quarter?",
        "reason": "The database has no marketing campaign expenditure.",
    },
    {
        "id": "U004",
        "question": "What was the total value of customer refunds last month?",
        "reason": "The database has no refund records.",
    },
    {
        "id": "U005",
        "question": "What is the age of each customer?",
        "reason": "The Customer table has no date-of-birth column.",
    },
]