# -*- coding: utf-8 -*-

import base64
import datetime
import io
import json
import numpy as np
import os
import pandas as pd
import re
import tempfile
from zipfile import ZipFile

from dash import Dash, dcc, html, callback_context
from dash.dependencies import Input, Output, State

# button: upload Excel Questionnarie
bt_up = dcc.Upload(
    html.Button("Click to Upload", id="btn"),
    id="upload-data",
)

# dropdown: year/s to parse (Excel Sheet/s)
# initialize empty
years_in_excel = {}
dd_years = dcc.Dropdown(
    id="my_years",
    placeholder="Year/s in Questionnarie",
    multi=True,
)

# button: upload Excel Mapping
bt_up_map = dcc.Upload(
    html.Button("Click to Upload", id="btn_map"),
    id="upload-map",
)

# button: download converted SDMX-csvs (can't be placed in dcc.Download ?)
bt_con_dwd = html.Button("Click to Download", id="btn-con-dwd")

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
# Build App
app = Dash(__name__, external_stylesheets=external_stylesheets)
# to deploy using WSGI server
server = app.server
# app tittle for web browser
app.title = "ESSPROS to SDMX-csv converter"

# App Layout
app.layout = html.Div([
    html.H6(
        "Expenditures and Receipts Excel to SDMX Conversor",
        style={'verticalAlign': 'bottom', 'fontWeight': 'bold'},
    ),
    html.Hr(),
    # div questionnarie
    html.Div([
        html.Div(
            ["Excel Questionnaire", bt_up],
            style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'},
        ),
        html.Div(
            ["Questionnaire Validation", html.Button("Click to Validate", id="btn-val")],
            style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'},
        ),
        html.Div(
            ["Select Year/s to Report", dd_years],
            style={'width': '35%', 'display': 'inline-block', 'verticalAlign': 'top'},
        ),
    ]),
    html.Hr(),
    # div mapping
    html.Div([
        html.Div(
            ["Excel Mapping DSD", bt_up_map],
            style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'},
        ),
        html.Div(
            ["Mapping Validation", html.Button("Click to Validate", id="btn-val-map")],
            style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'},
        ),
        html.Div(
            ["Conversion Execution", html.Button("Click to Convert", id="btn-exe-con")],
            style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'},
        ),
        html.Div(
            [
                "Conversion Download",
                bt_con_dwd,
                dcc.Download(id="data-download"),
            ],
            style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'},
        ),
    ]),
    # display output for UX
    html.Div(id='ux-display'),
    # hidden div: html ouput from load button
    html.Div(id='output-data-upload', style={'display': 'none'}),
    # hidden div to share excel_quest_df across
    html.Div(id='excel-quest-df', style={'display': 'none'}),
    # hidden div to share questionnarie sheet names across
    html.Div(id='excel-sheetnames', style={'display': 'none'}),
    # hidden div: html ouput from questionnarie validation
    html.Div(id='val-quest-output', style={'display': 'none'}),
    # hidden div to share reported years in questionnarie
    html.Div(id='years-report', style={'display': 'none'}),
    # hidden div to share quest reported years with proper schemes and codes
    html.Div(id='sheets-years-schemes', style={'display': 'none'}),
    # hidden div: html ouput from load map button
    html.Div(id='output-map-upload', style={'display': 'none'}),
    # hidden div to share excel_map_df across
    html.Div(id='excel-map-df', style={'display': 'none'}),
    # hidden div to share map sheet names across
    html.Div(id='map-sheetnames', style={'display': 'none'}),
    # hidden div: html ouput from mapping validation
    html.Div(id='val-map-output', style={'display': 'none'}),
    # hidden div to share mapping sheets (EXP and REC)
    html.Div(id='mapping-sheets', style={'display': 'none'}),
    # hidden div to share mapping sheet names for (EXP and REC)
    html.Div(id='mapping-exp-rec-sheetnames', style={'display': 'none'}),
    # hidden div to share mapping validation flag
    html.Div(id='map-val-flag', style={'display': 'none'}),
    # hidden div: html ouput from conversion
    html.Div(id='conversion-output', style={'display': 'none'}),
    # hidden div to share sdmx-csv EXP file
    html.Div(id='sdmx-csv-exp-output', style={'display': 'none'}),
    # hidden div to share sdmx-csv REC file
    html.Div(id='sdmx-csv-rec-output', style={'display': 'none'}),
    # hidden div to share conversion flag
    html.Div(id='conv-flag', style={'display': 'none'}),
    # hidden div to share union set of espross codes
    html.Div(id='union-set-codes', style={'display': 'none'}),
    # hidden div: html ouput from download
    html.Div(id='con-dwd-output', style={'display': 'none'}),
])

def parse_excel_file(contents, filename, date):
    # decoded as proposed in Dash Doc
    _, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        if 'xls' in filename:
            # Assume that the user uploaded an excel file
            quest_file = pd.ExcelFile(io.BytesIO(decoded))
            excel_df = quest_file.parse(sheet_name=None, header=2)
        else:
            # Warn user hasn't uploaded an excel file
            return (
                html.Div([
                    html.Hr(),
                    html.H6("Questionnarie must be an Excel file"),
                ]), ({}, {})
            )
    except Exception as e:
        print(e)
        # Warn user excel file wasn't parsed
        return (
            html.Div([
                html.Hr(),
                html.H6(f"There was an error processing {filename}"),
            ]), ({}, {})
        )
    
    # return ingestion message and parsed Excel
    return (
        html.Div([
            html.Hr(),
            html.H6(f"Uploaded Questionnarie is {filename}"),
            html.H6(f"Last modified datetime is {datetime.datetime.fromtimestamp(date)}"),
        ]),
        # special treatment: excel number of sheets
        (
            [excel_df[k].to_json(orient='split') for k in excel_df]
            if type(excel_df) is dict
            else [excel_df.to_json(orient='split')],
            quest_file.sheet_names
        )
    )

def parse_mapping_file(contents, filename, date):
    # decoded as proposed in Dash Doc
    _, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        if 'xls' in filename:
            # Assume that the user uploaded an excel file
            map_file = pd.ExcelFile(io.BytesIO(decoded))
            map_df = map_file.parse(sheet_name=None, header=6)
        else:
            # Warn user hasn't uploaded an excel file
            return (
                html.Div([
                    html.Hr(),
                    html.H6("SDMX Mapping must be provided in Excel"),
                ]), ({}, {})
            )
    except Exception as e:
        print(e)
        # Warn user excel file wasn't parsed
        return (
            html.Div([
                html.Hr(),
                html.H6(f"There was an error processing {filename}"),
            ]), ({}, {})
        )

    # return ingestion message and parsed Excel
    return (
        html.Div([
            html.Hr(),
            html.H6(f"Uploaded SDMX Mapping is {filename}"),
            html.H6(f"Last modified datetime is {datetime.datetime.fromtimestamp(date)}"),
        ]),
        # special treatment: excel number of sheets
        (
            [map_df[k].to_json(orient='split') for k in map_df]
            if type(map_df) is dict
            else [map_df.to_json(orient='split')],
            map_file.sheet_names
        )
    )

@app.callback(
    Output('output-data-upload', 'children'),
    Output("excel-quest-df", "children"),
    Output("excel-sheetnames", "children"),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('upload-data', 'last_modified'),
    prevent_initial_call=True,
)
def wrap_excel_parsing(loaded_file, file_name, file_last_mod):
    
    # coded as proposed in Dash Doc
    # callback sees changes in content only (eg: not same content with different filename)
    if loaded_file is not None:
        html_out, quest_json = parse_excel_file(loaded_file, file_name, file_last_mod)
        return html_out, quest_json[0], quest_json[1]

@app.callback(
    Output('output-map-upload', 'children'),
    Output("excel-map-df", "children"),
    Output("map-sheetnames", "children"),
    Input('upload-map', 'contents'),
    State('upload-map', 'filename'),
    State('upload-map', 'last_modified'),
    prevent_initial_call=True,
)
def wrap_mapping_parse(loaded_file, file_name, file_last_mod):
    
    # coded as proposed in Dash Doc
    # callback sees changes in content only (eg: not same content with different filename)
    if loaded_file is not None:
        html_out, map_json = parse_mapping_file(loaded_file, file_name, file_last_mod)
        return html_out, map_json[0], map_json[1]

@app.callback(
    Output('val-quest-output', 'children'),
    Output('years-report', 'children'),
    Output('sheets-years-schemes', 'children'),
    Input("btn-val", "n_clicks"),
    State("excel-quest-df", "children"),
    State("excel-sheetnames", "children"),
    prevent_initial_call=True,
)
def validate_questionnarie(_, parsed_quest, quest_sheetnames):
    flag_parsed = parsed_quest[0] if parsed_quest else None

    if not flag_parsed:
        return (
            html.Div([
                html.Hr(),
                html.H6("Please upload Excel Questionnarie first"),
            ]),
            {},
            []
        )

    # json into dict of df/s - questionnarie sheets
    quest_df = {
        k: pd.read_json(parsed_quest[i], orient='split')
        for i, k in enumerate(quest_sheetnames)
    }

    # extract years regex from sheetnames
    years_report = {
        k: re.findall(r'\d{4}', k)[0]
        for k in quest_sheetnames
        if re.findall(r'\d{4}', k)
    }

    # check if any 'scheme' in expected headers for all years
    schemes_report = [
        k for k in years_report
        if not quest_df[k].columns.str.contains(r'(?i)scheme').any()
    ]

    # verify ESSPROS codes for all years: 100 diff from 350 plausability
    num_codes = [
        k for k in years_report
        if not (
            250 < pd.to_numeric(
                quest_df[k].iloc[:,1], errors='coerce'
            ).notnull().sum() < 450
        )
    ]

    # years with proper header and ESSPROS codes
    years_scheme_code = years_report.copy()
    for year_no_scheme_or_code in set().union(schemes_report, num_codes):
        del years_scheme_code[year_no_scheme_or_code]

    # message (years in quest)
    years_msg = (
        f"Years reported in questionnarie {list(years_report.values())}"
        if years_report else "No years in questionnarie to report"
    )

    # message (proper header with schemes)
    schemes_msg = (
        f"Adjust header for sheet/s {schemes_report} in questionnarie"
        if schemes_report else ""
    )

    # message (proper aligned column with ESSPROS codes)
    num_codes_msg = (
        f"Adjust ESSPROS codes in column B for sheet/s {num_codes} in questionnarie"
        if num_codes else ""
    )

    # sheetnames list if ESSPROS codes duplicated
    dupli_codes = []
    for k in years_scheme_code:
        # all-transform to numeric
        quest_df[k] = quest_df[k].apply(pd.to_numeric, errors='coerce')
        # replace zeros with NaN for cleaning later
        quest_df[k].replace(0, np.nan, inplace=True)
        # retain column B name before dropping
        col_b_name = quest_df[k].columns[1]
        # standardize col_b_bame to 'ESSPROS_CODE'
        quest_df[k].rename(columns={col_b_name: 'ESSPROS_CODE'}, inplace=True)
        # drop columns if all NaN
        quest_df[k].dropna(axis='columns', how='all', inplace=True)
        # drop rows if missing numeric code; IMPORTANT --> loc 'ESSPROS_CODE'
        quest_df[k].drop(quest_df[k][
            quest_df[k].loc[:,'ESSPROS_CODE'].isnull()
        ].index, inplace=True)
        # cast numeric codes to integer type
        quest_df[k].loc[:,'ESSPROS_CODE'] = quest_df[k].loc[:,'ESSPROS_CODE'].astype("int64")
        # check for duplicated codes
        filter_duplicates = quest_df[k].loc[:,'ESSPROS_CODE'].duplicated()
        if filter_duplicates.any():
            dupli_codes.append(k)
            quest_df[k].drop(quest_df[k][filter_duplicates].index, inplace=True)

    # message (duplicated ESSPROS codes)
    duplicated_msg = (
        f"Eliminate duplicated ESSPROS codes for sheet/s {dupli_codes} in questionnarie"
        if dupli_codes else ""
    )

    # build ouput message
    output_msg = html.Div([
        html.Hr(),
        html.H6(years_msg),
        html.H6(schemes_msg),
        html.H6(num_codes_msg),
        html.H6(duplicated_msg),
    ])

    return (
        output_msg,
        json.dumps(years_scheme_code, indent = 4),
        [quest_df[k].to_json(orient='split') for k in years_scheme_code],
    )

@app.callback(
    Output("my_years", "options"),
    Input('years-report', 'children'),
    Input('upload-data', 'contents'),
    prevent_initial_call=True,
)
def update_dd_years(years_in_quest, _):
    triger_id = (
        callback_context.
        triggered[0]['prop_id'].
        split('.')[0]
    )
    
    # coded as proposed in Dash Doc (without PreventUpdate)
    if ( (not years_in_quest) | ('upload' in triger_id) ):
        return []

    return [
        {'label': v, 'value': k}
        for k, v in json.load(io.StringIO(years_in_quest)).items()
    ]

    # v for v in options if search_value in o["label"]

@app.callback(
    Output('val-map-output', 'children'),
    Output('mapping-sheets', 'children'),
    Output('mapping-exp-rec-sheetnames', 'children'),
    Output('map-val-flag', 'children'),
    Output('union-set-codes', 'children'),
    Input("btn-val-map", "n_clicks"),
    State("excel-map-df", "children"),
    State("map-sheetnames", "children"),
)
def validate_mapping(n_clicks, parsed_map, map_sheetnames):
    # initial call, map-val-flag: False
    if not n_clicks:
        return [], [], [], False, []

    flag_parsed = parsed_map[0] if parsed_map else None

    if not flag_parsed:
        return (
            html.Div([
                html.Hr(),
                html.H6("Please upload Excel Mapping first"),
            ]), [], [], False, []
        )

    # json into dict of df/s - mapping sheets
    mapping_df = {
        k: pd.read_json(parsed_map[i], orient='split')
        for i, k in enumerate(map_sheetnames)
    }

    # mapping must contain ('EXPEND' and 'RECEIPT')-like sheets
    map_sheets = {
        k: v
        for k in map_sheetnames
        for v in ['EXPEND', 'RECEIPT']
        if re.findall(f"(?i){v}", k)
    }

    # message (map_sheets must equal two)
    map_sheet_msg = (
        f"Mapping file sheets to be used in the conversion: {list(map_sheets.keys())}"
        if len(map_sheets) == 2
        else
        "There must be two sheets for 'EXPEND' and 'RECEIPT' in mapping file"
    )

    # check expected headers: 'CODE' (ESSPROS) and DSDs
    dsd_commons = [
        'CODE',
        'FREQ',
        'REF_AREA',
        'TIME_PERIOD',
        'OBS_VALUE',
        'UNIT',
        'UNIT_MULT',
    ]
    dsd_not_in_header = [
        k for k in map_sheets
        if not all(
            col in mapping_df[k].columns for col in dsd_commons
        )
    ] if len(map_sheets) == 2 else []
    
    # message (proper headers with DSD's)
    dsd_header_msg = (
        f"Adjust header for sheet/s {dsd_not_in_header} in mapping"
        if dsd_not_in_header else ""
    )

    # check that provided DSD's (EXP and REC) differ
    map_sheets_keys = list(map_sheets.keys())
    map_sheets_vals = list(map_sheets.values())
    dsd_not_differ = (
        set(
            mapping_df[map_sheets_keys[map_sheets_vals.index('EXPEND')]].columns
        ) ==
        set(
            mapping_df[map_sheets_keys[map_sheets_vals.index('RECEIPT')]].columns
        )
        if (
            (not dsd_not_in_header) & (len(map_sheets) == 2)
        ) else False
    )

    # message (EXP and REC differ)
    dsd_differ_msg = (
        "'EXPEND' and 'RECEIPT' columns structure must differ"
        if dsd_not_differ else ""
    )

    # ESSPROS number of codes plausability bounds
    num_codes_bound = {
        'EXPEND': [310 - 80, 310 + 80],
        'RECEIPT': [60 - 20, 60 + 20],
    }

    # verify ESSPROS codes for all years: 100 diff from 350 plausability
    num_codes = [
        k for k,v in map_sheets.items()
        if not (
            num_codes_bound[v][0] < pd.to_numeric(
                mapping_df[k].iloc[:,1], errors='coerce'
            ).notnull().sum() < num_codes_bound[v][1]
        )
    ] if (
        (not dsd_not_differ) & (not dsd_not_in_header) & (len(map_sheets) == 2)
    ) else []

    # message (proper aligned column with ESSPROS codes)
    num_codes_msg = (
        f"Adjust ESSPROS codes in column B for sheet/s {num_codes} in mapping"
        if num_codes else ""
    )

    # check if mapping validated for conversion
    map_val_flag = (
        (len(map_sheets) == 2) &
        (not dsd_not_in_header) &
        (not dsd_not_differ) &
        (not num_codes)
    )

    # set of EXPEND and RECEIPT codes
    set_of_codes = []
    # sheetnames list if ESSPROS codes duplicated
    dupli_codes = []
    # check for duplicates only if validated
    if map_val_flag:
        for k in map_sheets:
            # drop rows if missing numeric code
            mapping_df[k].drop(mapping_df[k][
                pd.to_numeric(mapping_df[k].CODE, errors='coerce').isnull()
            ].index, inplace=True)
            # cast numeric codes to integer type
            mapping_df[k].loc[:,"CODE"] = mapping_df[k].CODE.astype("int64")

            # check for duplicated codes
            filter_duplicates = mapping_df[k].CODE.duplicated()
            if filter_duplicates.any():
                dupli_codes.append(k)
                mapping_df[k].drop(
                    mapping_df[k][filter_duplicates].index, inplace=True
                )
            
            set_of_codes.append(set(mapping_df[k].CODE))

    # message (duplicated ESSPROS codes)
    duplicated_msg = (
        f"Eliminate duplicated ESSPROS codes for sheet/s {dupli_codes} in mapping"
        if dupli_codes else ""
    )

    # check empty intersection between EXPEND and RECEIPT
    codes_intersect = (
        set_of_codes[0] & set_of_codes[1]
        if set_of_codes else ()
    )

    # message (shared EXPEND and RECEIPT codes in mappings)
    code_intersect_msg = (
        f"Eliminate shared codes between sheets {list(map_sheets.keys())} in mapping"
        if codes_intersect else ""
    )

    # drop codes_intersect (in both EXPEND and RECEIPT)
    for esspros_code in codes_intersect:
        for k in map_sheets:
            mapping_df[k].drop(mapping_df[k][
                mapping_df[k].CODE == esspros_code
            ].index, inplace=True)

    # build ouput message
    output_msg = html.Div([
        html.Hr(),
        html.H6(map_sheet_msg),
        html.H6(dsd_header_msg),
        html.H6(dsd_differ_msg),
        html.H6(num_codes_msg),
        html.H6(duplicated_msg),
        html.H6(code_intersect_msg),
    ])

    return (
        output_msg,
        [mapping_df[k].to_json(orient='split') for k in map_sheets],
        json.dumps(map_sheets, indent = 4),
        map_val_flag,
        # union set
        list(set_of_codes[0].union(set_of_codes[1])) if set_of_codes else []
    )

# Hard-coded country map: Bosnia and Herzegovina
country_map = {
    r'(?i)\bCountry\b': 'BA',
    r'(?i)\bCountry_National_currency\b': 'BAM',
    r'(?i)\*': ''
}

# callback ejecucion de la conversion
@app.callback(
    Output('conversion-output', 'children'),
    Output('sdmx-csv-exp-output', 'children'),
    Output('sdmx-csv-rec-output', 'children'),
    Output('conv-flag', 'children'),
    Input("btn-exe-con", "n_clicks"),
    State("my_years", "value"),
    State("map-val-flag", "children"),
    State('sheets-years-schemes', 'children'),
    State('years-report', 'children'),
    State('mapping-sheets', 'children'),
    State('mapping-exp-rec-sheetnames', 'children'),
    State('union-set-codes', 'children'),
)
def execute_conversion(
    n_clicks,
    years_selected,
    map_val_flag,
    quest_sheets,
    quest_years,
    map_sheets,
    exp_rec_ref,
    union_set_codes,
):
    # initial call, conv-flag: False
    if not n_clicks:
        return [], [], [], False

    if not years_selected:
        return (
            html.Div([
                html.Hr(),
                html.H6("Upload and validate questionnarie, and then select years to convert"),
            ]), [], [], False
        )

    if not map_val_flag:
        return (
            html.Div([
                html.Hr(),
                html.H6("Upload and validate mapping first"),
            ]), [], [], False
        )

    # quest_years: json to dict
    quest_years = json.load(io.StringIO(quest_years))

    # quest_df: json to dict of dfs
    quest_df = {
        k: pd.read_json(quest_sheets[i], orient='split')
        for i, k in enumerate(quest_years)
        if k in years_selected
    }
    
    # map_df: json to dict of dfs
    map_df = {
        v: pd.read_json(map_sheets[i], orient='split')
        for i, v in enumerate(
            json.load(io.StringIO(exp_rec_ref)).values()
        )
    }

    # message (reported schemes per year)
    schemes_year_msg = {}
    # message (any scheme and code not mapped per year)
    scheme_not_map_year_msg = {}

    # actual conversion comming below
    output_rows = []
    for y in years_selected:

        # reported schemes for the year
        rep_scheme = quest_df[y].columns[
            quest_df[y].columns.str.contains(r'(?i)scheme')
        ]
        # SDMX schemes codelist map
        scheme_map = {
            k: 'SCH0' + re.findall(r'\d{2}', k)[0]
            if re.findall(r'\d{2}', k) else '_T'
            for k in rep_scheme
        }
        # quest_df[y] codes not in map
        quest_y_map_dif = set(quest_df[y].ESSPROS_CODE) - set(union_set_codes)
        # y-reported schemes not map
        scheme_y_not_map = []

        # replace proper year in mapping dfs
        map_df['EXPEND']['TIME_PERIOD'] = quest_years[y]
        map_df['RECEIPT']['TIME_PERIOD'] = quest_years[y]

        for _, row in quest_df[y].iterrows():
            
            # check if not mapped
            is_not_map = row['ESSPROS_CODE'] in quest_y_map_dif
            # check if schemes empty
            empty_schemes = row[rep_scheme].isnull()
            # skip row if not map or all schemes empty
            # track if any scheme not mapped
            if ( is_not_map & ( (~empty_schemes).any() ) ):
                scheme_y_not_map.append(int(row['ESSPROS_CODE']))
                continue
            elif (is_not_map | empty_schemes.all()):
                continue
            
            # exp or rec logic
            exp_mask = map_df['EXPEND'].CODE == row['ESSPROS_CODE']
            if exp_mask.any():
                row_map = map_df['EXPEND'][exp_mask]
            else:
                rec_mask = map_df['RECEIPT'].CODE == row['ESSPROS_CODE']
                row_map = map_df['RECEIPT'][rec_mask]

            # assumes [2:] are DSD columns
            entry_dict = row_map.iloc[:,2:].replace(
                country_map, regex=True
            ).to_dict('records')[0]

            # loop through schemes (not empty)
            for index, value in row[rep_scheme][~empty_schemes].iteritems():
                entry_dict['OBS_VALUE'] = round(value, 2)
                entry_dict['CUSTOM_BREAKDOWN'] = scheme_map[index]
                output_rows.append(entry_dict.copy())

        # message reported schemes
        schemes_year_msg[quest_years[y]] = (
            str(list(rep_scheme)) if list(rep_scheme)
            else "Empty schemes reported"
        )
        # message any scheme and code not mapped
        scheme_not_map_year_msg[quest_years[y]] = (
            str(scheme_y_not_map) if scheme_y_not_map
            else ""
        )

    # `scheme_not_map_year_msg`: re-assemble
    scheme_not_map_msg_list = list(
        {
            k: v for k, v in scheme_not_map_year_msg.items() if v != ""
        }.items()
    )

    # wrap message (scheme not map per year)
    wrap_not_map_msg = "\n".join(
        np.concatenate(scheme_not_map_msg_list)
        if scheme_not_map_msg_list else []
    )

    # build ouput message
    output_msg = html.Div([
        html.Hr(),
        html.H6(
            "Converted Schemes per year:",
            style={'fontWeight': 'bold', 'textDecoration': 'underline'},
        ),
        html.H6(
            "\n".join(
                np.concatenate(list(schemes_year_msg.items()))
            ),
            style={'whiteSpace': 'pre-line', 'fontSize': '12'},
        ),
        html.H6(
            "ESSPROS codes without mapping:" if wrap_not_map_msg else "",
            style={'fontWeight': 'bold', 'textDecoration': 'underline'},
        ),
        html.H6(
            wrap_not_map_msg if wrap_not_map_msg else "",
            style={'whiteSpace': 'pre-line', 'fontSize': '12'}
        ),
    ])

    # separate output on mapped columns: EXP and REC
    exp_rows = [
        row for row in output_rows
        if len(row) == map_df['EXPEND'].shape[1] - 2
    ]
    rec_rows = [
        row for row in output_rows
        if len(row) == map_df['RECEIPT'].shape[1] - 2
    ]

    # build output dfs


    return (
        output_msg,
        [json.dumps(r, indent = 4) for r in exp_rows],
        [json.dumps(r, indent = 4) for r in rec_rows],
        True
    )

# helper function for closing temporary files - stackoverflow
def close_tmp_file(tf):
    try:
        os.unlink(tf.name)
        tf.close()
    except:
        pass

# callback download conversion (deployable)
@app.callback(
    Output('con-dwd-output', 'children'),
    Output('data-download', 'data'),
    Input("btn-con-dwd", "n_clicks"),
    State('conv-flag', 'children'),
    State('sdmx-csv-exp-output', 'children'),
    State('sdmx-csv-rec-output', 'children'),
    prevent_initial_call=True,
)
def download_conversion(_, conv_flag, exp_rows, rec_rows):

    if not conv_flag:
        return (
            html.Div([
                html.Hr(),
                html.H6("Please execute first a successful conversion"),
            ]),
            None
        )

    # dictionary with output rows
    rows_dict = {}
    # exp_rows: list of dicts from json loads
    rows_dict["EXP_SDMX"] = [json.load(io.StringIO(r)) for r in exp_rows]
    # rec_rows: list of dicts from json loads
    rows_dict["REC_SDMX"] = [json.load(io.StringIO(r)) for r in rec_rows]
    
    # exp dsd columns: all list elements keys should be same
    exp_df = pd.DataFrame(columns=[k for k in rows_dict["EXP_SDMX"][0]])
    # rec dsd columns: all list elements keys should be same
    rec_df = pd.DataFrame(columns=[k for k in rows_dict["REC_SDMX"][0]])

    # add df_dict to zip_dict using temporary files - stackoverflow
    df_dict = {"EXP_SDMX": exp_df, "REC_SDMX": rec_df}
    zip_dict = {}
    for name, df in df_dict.items():
        df_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        df.append(rows_dict[name]).to_csv(df_temp_file.name, index=False)
        df_temp_file.flush()
        zip_dict[name] = df_temp_file.name

    zip_tf = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    zf = ZipFile(zip_tf, mode='w')
    for name, fn in zip_dict.items():
        zf.write(fn, f"{name}.csv")

    # close uploaded temporary files
    zf.close()
    zip_tf.flush()
    zip_tf.seek(0)

    [close_tmp_file(_tf) for _tf in zip_dict]
    # close_tmp_file(zip_tf) # the app works if I remove this

    return (
        html.Div([
            html.Hr(),
            html.H6("Zip downloaded with SDMX-csv files"),
        ]),
        dcc.send_file(zip_tf.name, filename="EXP_REC_SDMX.zip")
    )

@app.callback(
    Output('ux-display', 'children'),
    Input('output-data-upload', 'children'),
    Input('val-quest-output', 'children'),
    Input('output-map-upload', 'children'),
    Input('val-map-output', 'children'),
    Input('conversion-output', 'children'),
    Input('con-dwd-output', 'children'),
    prevent_initial_call=True,
)
def update_output(
    quest_load, quest_val, map_load, map_val, conv_out, dwd_out
):

    triger_id = (
        callback_context.
        triggered[0]['prop_id'].
        split('.')[0]
    )

    if 'data-upload' in triger_id:
        return quest_load
    elif 'quest-output' in triger_id:
        return quest_val
    elif 'map-upload' in triger_id:
        return map_load
    elif 'map-output' in triger_id:
        return map_val
    elif 'conversion-output' in triger_id:
        return conv_out
    else:
        return dwd_out

if __name__ == '__main__':
    app.run_server(debug=True)