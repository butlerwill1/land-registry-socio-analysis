import pandas as pd
import regex as re
#%% ---------------------------------------------------------------------------------------------------
#                                   Functions for Pandas operations
# -----------------------------------------------------------------------------------------------------
indicators_to_aggregate = ['Overall', 'Income', 'Employment', 'Education',
                           'Health', 'Crime', 'HousingBarriers', 'Environment']

def create_imd_column_mapping():
    """
    Create a mapping dictionary to rename IMD_population_all_indices.csv columns
    to standardized short names for easier processing.

    Returns:
        dict: Mapping from original column names to standardized names
    """
    mapping = {
        'LSOA code (2021)': 'LSOACode',
        'LSOA name (2021)': 'AreaName',
        'Local Authority District code (2024)': 'LADCode',
        'Local Authority District name (2024)': 'LADName',

        # Overall IMD
        'Index of Multiple Deprivation (IMD) Score': 'OverallScore',
        'Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)': 'OverallRank',
        'Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)': 'OverallDecile',

        # Income
        'Income Score (rate)': 'IncomeScore',
        'Income Rank (where 1 is most deprived)': 'IncomeRank',
        'Income Decile (where 1 is most deprived 10% of LSOAs)': 'IncomeDecile',

        # Employment
        'Employment Score (rate)': 'EmploymentScore',
        'Employment Rank (where 1 is most deprived)': 'EmploymentRank',
        'Employment Decile (where 1 is most deprived 10% of LSOAs)': 'EmploymentDecile',

        # Education, Skills and Training
        'Education, Skills and Training Score': 'EducationScore',
        'Education, Skills and Training Rank (where 1 is most deprived)': 'EducationRank',
        'Education, Skills and Training Decile (where 1 is most deprived 10% of LSOAs)': 'EducationDecile',

        # Health Deprivation and Disability
        'Health Deprivation and Disability Score': 'HealthScore',
        'Health Deprivation and Disability Rank (where 1 is most deprived)': 'HealthRank',
        'Health Deprivation and Disability Decile (where 1 is most deprived 10% of LSOAs)': 'HealthDecile',

        # Crime
        'Crime Score': 'CrimeScore',
        'Crime Rank (where 1 is most deprived)': 'CrimeRank',
        'Crime Decile (where 1 is most deprived 10% of LSOAs)': 'CrimeDecile',

        # Barriers to Housing and Services
        'Barriers to Housing and Services Score': 'HousingBarriersScore',
        'Barriers to Housing and Services Rank (where 1 is most deprived)': 'HousingBarriersRank',
        'Barriers to Housing and Services Decile (where 1 is most deprived 10% of LSOAs)': 'HousingBarriersDecile',

        # Living Environment
        'Living Environment Score': 'EnvironmentScore',
        'Living Environment Rank (where 1 is most deprived)': 'EnvironmentRank',
        'Living Environment Decile (where 1 is most deprived 10% of LSOAs)': 'EnvironmentDecile',

        # Income Deprivation Affecting Children Index (IDACI)
        'Income Deprivation Affecting Children Index (IDACI) Score (rate)': 'IncomeDeprChildrenScore',
        'Income Deprivation Affecting Children Index (IDACI) Rank (where 1 is most deprived)': 'IncomeDeprChildrenRank',
        'Income Deprivation Affecting Children Index (IDACI) Decile (where 1 is most deprived 10% of LSOAs)': 'IncomeDeprChildrenDecile',

        # Income Deprivation Affecting Older People (IDAOPI)
        'Income Deprivation Affecting Older People (IDAOPI) Score (rate)': 'IncomeDeprOlderScore',
        'Income Deprivation Affecting Older People (IDAOPI) Rank (where 1 is most deprived)': 'IncomeDeprOlderRank',
        'Income Deprivation Affecting Older People (IDAOPI) Decile (where 1 is most deprived 10% of LSOAs)': 'IncomeDeprOlderDecile',

        # Children and Young People Sub-domain
        'Children and Young People Sub-domain Score': 'Services4YoungScore',
        'Children and Young People Sub-domain Rank (where 1 is most deprived)': 'Services4YoungRank',
        'Children and Young People Sub-domain Decile (where 1 is most deprived 10% of LSO': 'Services4YoungDecile',

        # Adult Skills Sub-domain
        'Adult Skills Sub-domain Score': 'AdultSkillsScore',
        'Adult Skills Sub-domain Rank (where 1 is most deprived)': 'AdultSkillsRank',
        'Adult Skills Sub-domain Decile (where 1 is most deprived 10% of LSOAs)': 'AdultSkillsDecile',

        # Geographical Barriers Sub-domain
        'Geographical Barriers Sub-domain Score': 'GeographicalBarriersScore',
        'Geographical Barriers Sub-domain Rank (where 1 is most deprived)': 'GeographicalBarriersRank',
        'Geographical Barriers Sub-domain Decile (where 1 is most deprived 10% of LSOAs)': 'GeographicalBarriersDecile',

        # Wider Barriers Sub-domain
        'Wider Barriers Sub-domain Score': 'WiderBarriersScore',
        'Wider Barriers Sub-domain Rank (where 1 is most deprived)': 'WiderBarriersRank',
        'Wider Barriers Sub-domain Decile (where 1 is most deprived 10% of LSOAs)': 'WiderBarriersDecile',

        # Indoors Sub-domain
        'Indoors Sub-domain Score': 'IndoorLivingScore',
        'Indoors Sub-domain Rank (where 1 is most deprived)': 'IndoorLivingRank',
        'Indoors Sub-domain Decile (where 1 is most deprived 10% of LSOAs)': 'IndoorLivingDecile',

        # Outdoors Sub-domain
        'Outdoors Sub-domain Score': 'OutdoorLivingScore',
        'Outdoors Sub-domain Rank (where 1 is most deprived)': 'OutdoorLivingRank',
        'Outdoors Sub-domain Decile (where 1 is most deprived 10% of LSOAs)': 'OutdoorLivingDecile',

        # Population
        'Total population: mid 2022': 'TotalPopulation',
        'Dependent Children aged 0-15: mid 2022': 'DependentChildren',
        'Older population aged 60 and over: mid 2022': 'Population60Plus',
        'Working age population 18-66 (for use with Employment Deprivation Domain): mid 2022': 'WorkingAgePopulation'
    }

    return mapping

def postcode_socio_grouby_agg(x):
    """
    Aggregate LSOA-level socio-economic indicators to postcode district level.

    Takes a grouped DataFrame (by PostDist) and calculates:
    - Basic geometry and area information
    - Population statistics
    - Aggregated deprivation scores (mean, median, min, max)
    - Aggregated ranks for each indicator

    Args:
        x: DataFrame group containing LSOA-level data for one postcode district

    Returns:
        pd.Series: Aggregated statistics for the postcode district
    """
    d = {}
    d['geometry'] = x['postcode_dist_geometry'].iloc[0]
    d['AreaName'] = x['LADName'].iloc[0] if 'LADName' in x.columns else x.get('LADnm', ['Unknown']).iloc[0]
    d['CountLowLevelAreas'] = x.shape[0]
    d['AreaKm2'] = x['AreaKm2'].iloc[0]

    # Population aggregation
    d['TotalPopulation'] = x['TotalPopulation'].sum()
    d['DependentChildren'] = x['DependentChildren'].sum()
    d['Population60Plus'] = x['Population60Plus'].sum()
    d['WorkingAgePopulation'] = x['WorkingAgePopulation'].sum()

    # Calculate percentages
    if d['TotalPopulation'] > 0:
        d['DependentChildren%'] = round(d['DependentChildren'] * 100 / d['TotalPopulation'], 2)
        d['Population60Plus%'] = round(d['Population60Plus'] * 100 / d['TotalPopulation'], 2)
        d['WorkingAgePopulation%'] = round(d['WorkingAgePopulation'] * 100 / d['TotalPopulation'], 2)
    else:
        d['DependentChildren%'] = 0
        d['Population60Plus%'] = 0
        d['WorkingAgePopulation%'] = 0

    d['PopulationDensity'] = round(d['TotalPopulation'] / d['AreaKm2'], 2) if d['AreaKm2'] > 0 else 0

    # Aggregate socio-economic indicators
    # For each indicator, calculate mean, median, min, max for Scores and mean for Ranks
    for indicator in indicators_to_aggregate:
        score_col = f'{indicator}Score'
        rank_col = f'{indicator}Rank'

        if score_col in x.columns:
            d[f'{indicator}Avg'] = round(x[score_col].mean(), 2)
            d[f'{indicator}Median'] = round(x[score_col].median(), 2)
            d[f'{indicator}Min'] = round(x[score_col].min(), 2)
            d[f'{indicator}Max'] = round(x[score_col].max(), 2)

        if rank_col in x.columns:
            d[f'{indicator}RankAvg'] = round(x[rank_col].mean(), 2)

    return pd.Series(d, index=list(d.keys()))

def check_districts(unique_districts):

    unique_areas = sorted(set([re.sub(r'[^A-Za-z]', '', x) for x in unique_districts]))


    for area in unique_areas:
        incremental_increase = True

        # Find all of the districts for a certain area
        related_districts = set([district for district in unique_districts if re.sub(r'[^A-Za-z]', '', district) == area])

        # Find all the numbers of that district, e.g. BR1, BR2, BR3 etc = [1, 2, 3]
        nums_of_districts = [''.join(re.findall(r'\d+',district)) for district in related_districts]
        
        # Turn this into an ordered set of integers
        nums_of_districts = sorted([int(number) for number in nums_of_districts if number != ''])


        if len(nums_of_districts) == 0:
            print(f'There are no District numbers for area {area}')
            continue

        first_number = nums_of_districts[0]

        if first_number not in [0, 1]:
            print(f' Districts in Area {area} do not start with 0 or 1: {nums_of_districts}')

        for num in nums_of_districts:
            if num != first_number:
                if num != previous_num + 1:
                    incremental_increase = False
        
            previous_num = num
        
        if incremental_increase == False:
            print(f' Districts in Area {area} do not increase incrementally: {nums_of_districts}')



def clean_socio_columns(column_name):
    
    replacements = {
        'IMD' : 'Overall',
        'Inc' : 'Income',
        'Emp' : 'Employment',
        'HDD' : 'Health',
        'Cri' : 'Crime',
        'BHS' : 'HousingBarriers',
        'Env' : 'Environment',
        'Edu' : 'Education',
        'IDC' : 'IncomeDeprChildren',
        'IDO' : 'IncomeDeprOlder',
        'CYP' : 'Services4Young',
        'AS' : 'AdultSkills',
        'GB' : 'GeographicalBarriers',
        'WB' : 'WiderBarriers',
        'Ind' : 'IndoorLiving',
        'Out' : 'OutdoorLiving'
    }
    for key, value in replacements.items():
        column_name = column_name.replace(key, value)
    
    return column_name

def clean_district_columns(columns):
    column_list = []
    for column in columns:
        if column == 'geometry':
            column_list.append(column)
            continue
        
        if '_' not in column:
            column = column[0].upper() + column[1:]
            column_list.append(column)
            continue

        parts = column.split('_')

        parts_list = []

        for part in parts:
            parts_list.append(part.title())
        
        column_list.append(''.join(parts_list))
    
    return column_list