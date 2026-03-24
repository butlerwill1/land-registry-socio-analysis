import pandas as pd
import regex as re
#%% ---------------------------------------------------------------------------------------------------
#                                   Functions for Pandas operations
# -----------------------------------------------------------------------------------------------------
indicators_to_aggregate = ['Overall', 'Income', 'Education', 
                           'Crime', 'Environment', 'GeographicalBarriers',
                           'IndoorLiving']

def postcode_socio_grouby_agg(x):

    d = {}
    d['geometry'] = x['postcode_dist_geometry'].iloc[0]
    d['AreaName'] = x['LADnm'].iloc[0]
    d['Locale'] = x['Locale'].iloc[0]
    d['CountLowLevelAreas'] = x.shape[0]
    d['AreaKm2'] = x['AreaKm2'].iloc[0]
    d['Population'] = x['TotPop'].sum()
    d['Population16-59%'] = round(x['Pop16_59'].sum() * 100 / d['Population'], 2)
    d['Population60+%'] = round(x['Pop60+'].sum() * 100 / d['Population'], 2)
    d['PopulationDensity'] = round(d['Population'] / d['AreaKm2'], 2)

    # Weighted Score of multiple factors, weightings can be found in "English_Socio_Economic.md

    for indicator in indicators_to_aggregate:
        d[f'{indicator}Avg'] = round(x[f'{indicator}Score'].mean(),2)
        d[f'{indicator}RankAvg'] = round(x[f'{indicator}Rank'].mean(),2)
        d[f'{indicator}Median'] = round(x[f'{indicator}Score'].median(),2)
        d[f'{indicator}Min'] = round(x[f'{indicator}Score'].min(),2)
        d[f'{indicator}Max'] = round(x[f'{indicator}Score'].max(),2)


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