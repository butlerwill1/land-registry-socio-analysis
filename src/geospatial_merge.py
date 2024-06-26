#%%
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import src.functions as func
import importlib
import os
importlib.reload(func)
#%% ---------------------------------------------------------------------------------------------------
#                Merge together Postcode and Socio Economic Indicator data on their polygons
# -----------------------------------------------------------------------------------------------------
#%% Import Polygon dataset that defines each Postcode District

postcode_dist_poly = gpd.read_file("GB_Postcodes/PostalDistrict.shp")

postcode_dist_poly['AreaKm2'] = postcode_dist_poly.geometry.area / 1000000

print(postcode_dist_poly.crs)

# Convert into a geograhic CRS (Latitude and Longitude in Degrees)
postcode_dist_poly = postcode_dist_poly.to_crs("EPSG:4326")

# Rename the geometry to another column so that you can merge it back later after the aggregation
postcode_dist_poly['postcode_dist_geometry'] = postcode_dist_poly.geometry

# %% Import the 2019 socio-economic dataset containing the polygons of Lower layer super output areas. 
# These are smaller than postcode districtsthis
# In this dataset, an area with a rank of 1 is the most deprived, and it will have the highest score.
# E.g. An area with a high crime rate will have a high score

socio_economic = gpd.read_file("English_IMD_2019/IMD_2019.shp")
print(socio_economic.crs)

# Rename the columns of the dataset from Abbreviations to be more understandable
renaming_dict = {col: func.clean_socio_columns(col) for col in socio_economic.columns}
renaming_dict['lsoa11nmw'] = 'AreaName'
              
socio_economic = socio_economic.rename(columns=renaming_dict)
socio_economic = socio_economic.rename(columns={'OverallRank0': 'OverallRank'})

# Convert into a geograhic CRS (Latitude and Longitude in Degrees)
socio_economic = socio_economic.to_crs("EPSG:4326")

# %% Do a spatial join where the smaller socio economic Lower-Layer Super Output Areas (LSOAs) are within the
# postcode district polygons. The op = 'within' argument means the socio_economic polygon must be completely inside 
# a postcode distribution polygon.

postcode_socio_economic = gpd.sjoin(socio_economic, postcode_dist_poly, how='inner', op='within')

#%% Now do a spatial join keeping the geometry of the low level smaller areas of the socio economic data
# This is used to provide more granualar socio economic insight into the smaller areas, whilst knowing which 
# postcode district each Lower-Layer Super Output Area (LSOA) is in. 
# The left join ensures that every line of the socio economic is kept

socio_economic_postcode = gpd.sjoin(socio_economic, postcode_dist_poly, how='left', op='within')

socio_economic_postcode.drop(columns=['postcode_dist_geometry']).\
    to_file("socio_economic_postcode.gpkg", layer='socio', driver="GPKG", if_exists='replace')

#%% Aggregate the dataset to the postcode level, averaging the Lower-Layer Super Output Areas (LSOAs) up to the 
# postcode district areas

aggregated_data = postcode_socio_economic.groupby("PostDist").apply(func.postcode_socio_grouby_agg).reset_index()

#%% Pick up the dataset from the Groupby Aggregations on the land registry dataset
# This dataset contains no geometry data, only the string code Postcode district

district_transaction_groupby = pd.read_csv("District_Transaction_Groupby%.csv")

#%% Merge the data of socio economic indicators now aggregated up to the district level onto 
# the transaction data which is also aggregated to the district level

district_groupby_socio_economic = pd.merge(district_transaction_groupby, aggregated_data, 
                                           how='left', left_on='postcode_district',
                                           right_on='PostDist')

# %% After the aggregation, ensure the dataframe is a geodataframe

district_groupby_socio_economic_gdf = gpd.GeoDataFrame(district_groupby_socio_economic, geometry='geometry')
# %% This dataframe will be used to show the most recent transaction stats and aggregated
# socio economic data for each Postcode district. Therefore we only need the most recent years worth of data

district_groupby_socio_economic_gdf = district_groupby_socio_economic_gdf[ \
            (district_groupby_socio_economic_gdf['PostDist'].notna())&
            (district_groupby_socio_economic_gdf['year']==2023)&
            (district_groupby_socio_economic_gdf['PostDist']!='Unknown')]
#%%
cols = ['postcode_district', 'is_london?', 'property_type',
       'year', 'num_transactions', 'avg_price',  '50th_percentile_price',
       'postcode_area', '5YearAvg%PriceInc', 'PostDist', 'geometry',
       'AreaName',  'Population','PopulationDensity', 'OverallAvg',
       'IncomeAvg',
       'EducationAvg', 'CrimeAvg', 'EnvironmentAvg', 'GeographicalBarriersAvg', 'IndoorLivingAvg']

district_groupby_socio_economic_gdf.drop(columns=['Unnamed: 0']).\
    to_file("district_groupby_socio_economic.gpkg", layer='socio', driver="GPKG", if_exists='replace')

#%%
print(f'File Size = {round(os.path.getsize("district_groupby_socio_economic.gpkg")/1000000, 2)}Mb')
# %%-----------------------------------------------------------------------------------------------
#                                                Sample Graphs
# -------------------------------------------------------------------------------------------------
# test = district_groupby_socio_economic[(district_groupby_socio_economic['is_london?']!='Outside London')&(district_groupby_socio_economic['property_type']=='F')]
# plt.title("Population Density Vs Number of transactions")
# plt.xlabel("Population Density")
# plt.ylabel("Number of Transactions")

# plt.scatter(test['PopulationDensity'],test['num_transactions'])
# # %%
# test = district_groupby_socio_economic[(district_groupby_socio_economic['is_london?']!='Outside London')&(district_groupby_socio_economic['property_type']=='F')]
# plt.title("CountLowLevelAreas Vs AreaKm2")
# plt.xlabel("CountLowLevelAreas")
# plt.ylabel("AreaKm2")

# plt.scatter(test['CountLowLevelAreas'],test['AreaKm2'])
# %%
socio_economic_reduced_cols = ['AreaName', 
       'Overall_Rank', 
       'IncomeScore',
       'EmploymentScore', 'EducationScore', 
       'HealthScore', 'CrimeScore', 'HousingBarriersScore', 'EnvironmentScore','IncomeDeprChildrenScore', 'IncomeDeprOlderScore', 'IncomeDeprOlderRank',
       'IncomeDeprOlderDec', 'Services4YoungScore', 'AdultSkillsScore', 'GeographicalBarriersScore',
       'WiderBarriersScore', 
       'IndoorLivingScore', 
       'OutdoorLivingScore', 'TotPop', 'Pop16_59', 'Pop60+', 'WorkPop', 'geometry', 'index_right',
       'DistID', 'PostDist', 'PostArea',
       'AreaKm2']