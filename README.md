# Immo Eliza - Data Collection

- Repository: `immo-eliza-scraping`
- Type: `Consolidation`
- Duration: `5 days`
- Deadline: `11/10/2024 4:00 PM`
- Team: Solo

## Learning Objectives

Use Python to collect as much data as possible.

At the end of this (sub)project, you will:
- Be able to scrape a website
- Be able to build a dataset from scratch


## The Mission

The real estate company "Immo Eliza" wants to develop a machine learning model to make price predictions on real estate sales in Belgium. They hired you to help with the entire pipeline. [Immoweb](https://www.immoweb.be/nl) is a commonly used website for Belgian properties.

Your first task is to build a dataset that gathers information about at least 10000 properties all over Belgium. This dataset will be used later to train your prediction model.

The final dataset should be a `csv` file with at least the following 18 columns:
- Property ID
- Locality name
- Postal code
- Price
- Type of property (house or apartment)
- Subtype of property (bungalow, chalet, mansion, ...)
- Type of sale (_note_: exclude life sales)
- Number of rooms
- Living area (area in m²)
- Equipped kitchen (0/1)
- Furnished (0/1)
- Open fire (0/1)
- Terrace (area in m² or null if no terrace)
- Garden (area in m² or null if no garden)
- Number of facades
- Swimming pool (0/1)
- State of building (new, to be renovated, ...)

## Must-have features (for the dataset)

- The data should have properties across all Belgium
- There should be at minimum unique 10000 data points
- Missing information is initially encoded with `None`
- Whenever possible, record only numerical values (for example, instead of defining whether the kitchen is equipped using `"Yes"` or `"No"`, use binary values instead)
- Use appropriate and consistent column names for your variables (those will be key to training and understanding your model later on)
- No duplicates
- No empty rows

## Installation
You can install all the package dependencies listed in the requirements.txt file.

## Comments
The property subtype is not explicitly extracted as a separate csv column.