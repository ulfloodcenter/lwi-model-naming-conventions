# LWI Stream Naming Convention Example code

## Setup

### Download NHDPlus seemless geodatabase

From [https://www.epa.gov/waterdata/nhdplus-national-data](https://www.epa.gov/waterdata/nhdplus-national-data)

```
https://s3.amazonaws.com/edap-nhdplus/NHDPlusV21/Data/NationalData/NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z
```

### Uncompress

```
7z x NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z
```

### Export to SQLite

Export these layers:
* NHDFlowline_Network
* PlusFlow

```
ogr2ogr -f "SQLite" NHDFlowline_Network.sqlite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb NHDFlowline_Network
ogr2ogr -f "SQLite" NHD_PlusFlow.sqlite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb PlusFlow
```

### Add indexes for fast searching

#### NHDFlowline_Network

```
sqlite3 NHDFlowline_Network.sqlite \
"create index if not exists nhd_flow_reachcode_idx on nhdflowline_network (reachcode); \
create index if not exists nhd_flow_comid_idx on nhdflowline_network (comid);"
```

#### PlusFlow

```
sqlite3 NHD_PlusFlow.sqlite \
"create index if not exists nhd_plusflow_tocomid_idx on plusflow (tocomid); \
create index if not exists nhd_plusflow_fromcomid_idx on plusflow (fromcomid);"
```

## How to Use

### Label streams
```
NHD_FLOWLINE=/path/to/NHDFlowline_Network.sqlite NHD_PLUSFLOW=/path/to/NHD_PlusFlow.sqlite python stream_naming_convention_experiments_label.py
```
Output will be stored in a directory named `output`.

### Concatenate output into one file
```
tail -q -n +2 *.csv > /tmp/LA_HUC8_stream_labels.csv
head -n 1 AA_03180004.csv | cat - /tmp/LA_HUC8_stream_labels.csv > LA_HUC8_stream_labels.csv
rm /tmp/LA_HUC8_stream_labels.csv
```

### Load CSV into your GIS and join to NHD Flowline layer

## Example data

Example output that has been joined to NHD Flowlines for HUC8s in the state of Louisiana can be found [here](https://services9.arcgis.com/SfvtKAxCn62UWpRg/arcgis/rest/services/LWI_LabeledNHDStreams_2020_09_10/FeatureServer).
