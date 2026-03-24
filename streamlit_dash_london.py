#%%
import streamlit as st
import folium
from folium.features import GeoJson, GeoJsonTooltip
import geopandas as gpd
from streamlit_folium import st_folium
import altair as alt
import pandas as pd
import sys
import os

# Import local utilities from src/local/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'local'))
import local_utils as func

st.set_page_config(layout="wide")
import branca.colormap as cm
#%%-----------------------------------------------------------------------------------------------------
#                           Streamlit Dashboard with Map and Price Change Graph
#-------------------------------------------------------------------------------------------------------

# Decorate the function with st.cache to only run it once and cache the result
@st.cache_data(show_spinner="Cache Miss")
def load_district_groupby_socio_economic():
    """Load the data source which contains the transaction data results by postcode district
    for 2023 with the 2019 socio economic data aggregated up to the district level joined on."""
    gdf = gpd.read_file('district_groupby_socio_economic_london.gpkg', layer='socio')
    # gdf['geometry'] = gdf['geometry'].apply(lambda x: x.wkt) 
    gdf.columns = func.clean_district_columns(gdf.columns)
    #gdf[(gdf['NumTransactions']<=100) & (gdf['Year']>= 2018)]
    return gdf

@st.cache_data(show_spinner="Cache Miss")
def load_socio_economic():
    """Load the 2019 socio-economic dataset with polygons the original smaller area level"""
    socio_economic = gpd.read_file("socio_economic_postcode_london.gpkg")

    return socio_economic

@st.cache_data(show_spinner="Cache Miss")
def load_price_graph():
    """Load the dataset of the average price of property for every year for each postcode district"""
    price_graph = pd.read_csv("district_groupby_price_graph.csv")
    price_graph.columns = func.clean_district_columns(price_graph.columns)
    return price_graph

@st.cache_data(show_spinner="Cache Miss")
def load_property_type_groupby():
    """Load the dataset of count of property transactions by Postcode District and Property Type"""
    property_type_groupby = pd.read_csv("property_type_groupby.csv")
    property_type_groupby.columns = func.clean_district_columns(property_type_groupby.columns)
    return property_type_groupby

district_groupby_socio_economic = load_district_groupby_socio_economic()
socio_economic = load_socio_economic()
price_graph = load_price_graph()
property_type_groupby = load_property_type_groupby()

# Function to apply style based on the value of choropleth_button
def apply_style(feature):
    if map_state == 'Choropleth':  # If the button is pressed, use choropleth style
        value = feature['properties'][choropleth_variable]
        return {
            'fillColor': linear(value),
            'color': 'rgba(0, 0, 0, 0.8)',
            'weight': 3,
            'dashArray': '5, 5', 
            'fillOpacity': 0.8
        }
    elif map_state == 'Area Investigation with Lower Level':  # If the button is not pressed, use the normal transparent style
        return {'fillColor': '#ffffff00', 'color': 'rgba(0, 0, 0, 0.6)', 'dashArray': '4, 3',  'weight': 2}

#%%
st.title('London Flat Transaction Dataset With Socio Economic Data')
st.markdown(f"[GitHub ReadMe](https://github.com/butlerwill1/housing_project/blob/main/readme.md) - \
            [Socio-economic data explanation](https://github.com/butlerwill1/housing_project/blob/main/Supporting%20Documents/SocioEconomicDataDoc.md) - \
            [Land Registry data explanation](https://github.com/butlerwill1/housing_project/blob/main/Supporting%20Documents/LandRegistryDataDoc.md)", unsafe_allow_html=True)

st.markdown("The socio economic data was measured on smaller geographic areas than a postcode district. These are the areas in red on the map. \
            Hover over these areas to reveal a tooltip showing stats about that area you can select in the select box below")
st.markdown("A higher score for the socio economic variables means the social problems are greater, e.g. a high crime score means there is a lot of crime, \
            a high education score means there are problems with educational deprivation")
st.markdown("The Transaction data is aggregated to the postcode district level, e.g. SW11, E4. These areas are represented by dashed \
            black lines on the map")
st.divider()

col1, col2 = st.columns(2)

with col1:
    
    socio_tooltip_choices = st.multiselect("Select the metrics you want to see from the 2019 Socio-economic data on the smaller red areas on the map", 
                                    sorted(socio_economic.columns),
                                  default=['AreaName', 'CrimeScore', 'EnvironmentScore'])
    
    col1A, col1B = st.columns(2)

    with col1A:
        map_state = st.selectbox("Select Map Usage", ['Area Investigation with Lower Level', 'Choropleth'])
    
    with col1B:
        choropleth_variable = st.selectbox("If Map type is Choropleth, select which variable to use",\
                                           sorted(district_groupby_socio_economic.select_dtypes(include=['number']).columns))

    if map_state == 'Area Investigation with Lower Level':
        
        district_choices = st.multiselect("Select Postcode Districts", 
                                  sorted(district_groupby_socio_economic['PostDist'].unique()),
                                  default='E3')

    elif map_state == 'Choropleth':
        district_choices = district_groupby_socio_economic['PostDist'].unique()
    #%%
    # num_transactions_threshold = st.slider("Select the Number of Transactions that is considered a good sample size for a Year")
    # Define a linear color scale
    linear = cm.linear.YlGnBu_09.scale(district_groupby_socio_economic[choropleth_variable].min(), 
                                    district_groupby_socio_economic[choropleth_variable].max())

    socio_economic = socio_economic[socio_economic['PostDist'].isin(district_choices)]
    #%%
    # Filter the GeoDataFrame based on the selected districts
    selected_districts = district_groupby_socio_economic[
        district_groupby_socio_economic['PostDist'].isin(district_choices)
    ]

    #%%
    if len(district_choices) == 0:
        st.warning("A District must be selected for the map to display")
    else:
        # Calculate the bounds of the selected polygons
        bounds = selected_districts.geometry.total_bounds
        minx, miny, maxx, maxy = bounds

        # Calculate the center of the bounds
        center = [(miny + maxy) / 2, (minx + maxx) / 2]

        # Initialize the map at the center of the bounds
        m = folium.Map(location=center)

        # Fit the map to the bounds
        m.fit_bounds([[miny, minx], [maxy, maxx]])

        default_display_cols = ['PostcodeDistrict', 'AvgPrice', '5YearAvg%PriceInc', 'CrimeAvg']

        #%%
        with col2:
            
            display_cols = st.multiselect("Select metrics from the Socio-economic data at the Postcode District Level, represented by black dotted areas on the map", 
                        options=sorted(district_groupby_socio_economic.columns), 
                        default=default_display_cols)

        # Define the tooltip for the postcode district level polygons
        postcode_tooltip = GeoJsonTooltip(
            fields=display_cols,
            aliases=display_cols,  # this is the label that will be shown in the tooltip
            localize=True,
            sticky=False,  # Set to True for the tooltip to follow the mouse
            labels=True,
            style="""
                background-color: #F0EFEF;
                border: 2px solid black;
                border-radius: 3px;
                box-shadow: 3px;
            """,
            max_width=800,
        )
       
        # Define the tooltip for the lower level socio economic polygons
        socio_tooltip = GeoJsonTooltip(
            fields=socio_tooltip_choices,
            aliases=socio_tooltip_choices,  # this is the label that will be shown in the tooltip
            localize=True,
            sticky=False,  # Set to True for the tooltip to follow the mouse
            labels=True,
            style="""
                background-color: #F0EFEF;
                border: 2px solid black;
                border-radius: 3px;
                box-shadow: 3px;
            """,
            max_width=800,
        )

        # Add the postcode district level polygons
        GeoJson(
            district_groupby_socio_economic[district_groupby_socio_economic['PostcodeDistrict'].isin(district_choices)],
            style_function=apply_style,  # Transparent polygons
            tooltip=postcode_tooltip
        ).add_to(m)

        #%%
        # Add the socio_economic dataset smaller polygons (the ones that fit within the postcode district)
        if map_state == 'Area Investigation with Lower Level':
            GeoJson(
                socio_economic,
                style_function=lambda x: {
                    'fillColor': 'rgba(255, 0, 0, 0.5)',  # Semi-transparent red
                    'color': 'rgba(255, 0, 0, 0.8)',       # Outline color, you can adjust as needed
                    'weight': 1,                            # Outline weight, you can adjust as needed
                    'fillOpacity': 0.5                      # Adjust fill opacity here as well
                },
                tooltip=socio_tooltip
            ).add_to(m)
    #%%
    
        st_folium(m, width=700)

        with col2:
            st.subheader("Comparison Table")
            # Display a dataframe of the selected metrics for comaprison between districts
            # st.dataframe(selected_districts[selected_districts['Year']==2023][display_cols],
            #             use_container_width=True,
            #             hide_index=True)
            
            # Display a graph of how the average price has changed over the years
            price_graph = price_graph[price_graph['PostcodeDistrict'].isin(district_choices)]
            price_graph['Year'] = pd.to_datetime(price_graph['Year'], format='%Y')

            
            # Create an interactive line chart
            chart = alt.Chart(price_graph).mark_line().encode(
                x='Year:T',  # The ':T' tells Altair that the data is temporal
                y=alt.Y('AvgPrice:Q', title='Average Price'),  # The ':Q' tells Altair that the data is quantitative
                color=alt.Color('PostcodeDistrict:N', legend=alt.Legend(title="Postcode District")),  # Different line for each postcode_district
                tooltip=['PostcodeDistrict:N', 'Year:T', 'AvgPrice:Q', 'NumTransactions:Q']  # Tooltips for interactivity
            ).properties(
                title = 'Change of Average Price of Postcode Districts Over time'
            ).interactive()

            # Display the chart in the Streamlit app
            st.altair_chart(chart, use_container_width=True)

            property_type_groupby = property_type_groupby[property_type_groupby['PostcodeDistrict'].isin(district_choices)]
            # Create an interactive line chart
            property_type_chart = alt.Chart(property_type_groupby).mark_bar().encode(
                x=alt.X('PropertyType:N', title='Property Type'),
                y=alt.Y('NumTransactions:Q', title='Num Transactions'),  # The ':Q' tells Altair that the data is quantitative
                column=alt.Column('PostcodeDistrict:N', title="Postcode District"),
                order=alt.Order('PropertyType:N', sort='ascending'),
                color=alt.Color('PostcodeDistrict:N', legend=alt.Legend(title="Postcode District")),  # Different line for each postcode_district
                tooltip=['PostcodeDistrict:N', 'PropertyType:N', 'NumTransactions:Q']  # Tooltips for interactivity
            ).properties(
                title = 'Number of Transactions by Property Type and Postcode District'
            ).interactive()

            # Display the chart in the Streamlit app
            st.altair_chart(property_type_chart)

            options = sorted(district_groupby_socio_economic.columns)
            st.subheader("Customisable Scatterplot of District")
            x_choice = st.selectbox("Choose the X axis variable", 
                                    options,
                                    index=options.index('CrimeAvg'))
            y_choice = st.selectbox("Choose the Y axis variable", 
                                    options,
                                    index=options.index("AvgPrice"))
            
            scatter_plot = alt.Chart(district_groupby_socio_economic.drop(columns='geometry')).mark_circle(size=60).encode(
            x=x_choice,
            y=y_choice,
            tooltip=['PostDist', x_choice, y_choice]  # Add more columns if needed
            ).interactive()

            # Display the chart in Streamlit
            st.altair_chart(scatter_plot, use_container_width=True)
# %%