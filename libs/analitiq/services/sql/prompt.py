TEXT_TO_SQL_PROMPT = """
You are a Data Analyst with a lot of experience in writing {dialect} queries in SQL.
You have received the following user query: {user_prompt}.
Given an user query, create a syntactically correct {dialect} SQL.
Unless the user specifies in the question a specific number of examples to obtain, query for at most {top_k} results using the LIMIT clause as per {dialect}. 
You can order the results to return the most informative data in the database.
Never query for all columns from a table. You must query only the columns that are needed to answer the question. 
Wrap each column name in double quotes (") to denote them as delimited identifiers.
Pay attention to use only the column names you can see in the tables below. Be careful to not query for columns that do not exist. 
Pay attention to which column is in which table.
Pay attention to use date('now') function to get the current date, if the question involves "today".
Qualify table names with a schema name {schema_name} in the SQL.
Here is a list of table names followed by list of columns, use only these tables and columns in SQL:
{table_info}

Write an initial draft of the query. Then double check the {dialect} query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins
- Keep in mind that underlying granular data may be very large. Try to obtain a summarized set of data from the database, but granular enough to answer the input question.

{format_instructions}
"""

RETURN_RELEVANT_TABLE_NAMES = """
Examine user query: {user_prompt}.
Your task is to select and return the names of the tables in a database that may contain information that could be relevant to the users query.
You will be provided with names of all tables in a database.
Use the user's query to determine the names of tables that may contain info the user is looking for from all the available tables in a database.
Return the names of relevant table in your output and comply with the requested formatting instructions. 
Return the names of ALL the SQL tables that MIGHT be relevant to the user query.


Names of all tables in a database:
{table_names_in_db}

{format_instructions}
"""