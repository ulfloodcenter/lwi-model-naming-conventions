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

#### NHDPlus V2.1

Export these layers:
* NHDFlowline_Network
* PlusFlow

```
ogr2ogr -f "SQLite" -dsco "SPATIALITE=YES" NHDFlowline_Network.spatialite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb NHDFlowline_Network
ogr2ogr -f "SQLite" NHD_PlusFlow.sqlite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb PlusFlow
```

#### NHDPlus HR

HUC4-based
```
ogr2ogr -skipfailures -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_1114_HU4_GDB/NHDPLUS_H_1114_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_1204_HU4_GDB/NHDPLUS_H_1204_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_1201_HU4_GDB/NHDPLUS_H_1201_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_0809_HU4_GDB/NHDPLUS_H_0809_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_0808_HU4_GDB/NHDPLUS_H_0808_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_0807_HU4_GDB/NHDPLUS_H_0807_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_0806_HU4_GDB/NHDPLUS_H_0806_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_0805_HU4_GDB/NHDPLUS_H_0805_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_0804_HU4_GDB/NHDPLUS_H_0804_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA && \
ogr2ogr -skipfailures -append -f "SQLite" -dsco "SPATIALITE=YES" NHDPlusHR-LA.sqlite NHDPLUS_H_0318_HU4_GDB/NHDPLUS_H_0318_HU4_GDB.gdb NHDFlowline NHDPlusFlow NHDPlusFlowlineVAA
```

### Add indexes for fast searching

#### NHDPlus v2.1: NHDFlowline_Network

```
sqlite3 NHDFlowline_Network.spatialite \
"create index if not exists nhd_flow_reachcode_idx on nhdflowline_network (reachcode COLLATE NOCASE); \
create index if not exists nhd_flow_comid_idx on nhdflowline_network (comid);"
```

#### NHDPlus v2.1: PlusFlow


```
sqlite3 NHD_PlusFlow.sqlite \
"create index if not exists nhd_plusflow_tocomid_idx on plusflow (tocomid); \
create index if not exists nhd_plusflow_fromcomid_idx on plusflow (fromcomid);"
```

#### NHDPlusHR

```
sqlite3 NHDPlusHR-LA.sqlite \
"create index if not exists nhdflowline_nhdplusid_idx on nhdflowline (nhdplusid); \
create index if not exists nhdplusflowlinevaa_nhdplusid_idx on nhdplusflowlinevaa (nhdplusid); \
create index if not exists nhdplusflow_fromnhdpid_idx on nhdplusflow(fromnhdpid); \
create index if not exists nhdplusflow_tonhdpid_idx on nhdplusflow(tonhdpid);"
```


## How to Use

### Label streams

NHDPlus V2:
```
python3 stream_naming_convention_experiments_label.py -f /path/to/NHDFlowline_Network.spatialite -p /path/to/NHD_PlusFlow.sqlite
```

NHDPlus HR:
```
python3 stream_naming_convention_experiments_label.py -f /path/to/NHDFlowline_Network.spatialite --nhdhr
```

> WARNING: NHDPlus HD seems to lack flow topology information in the NHDPlusFlow table needed to
> successfully run the LWI naming algorithm.

Note: To encode stream level labels as [base32](https://www.crockford.com/base32.html) instead of hexadecimal,
add the `--base32` command line option.

Output will be stored in a directory named `output`.

### Concatenate output into one file
```
tail -q -n +2 *.csv > /tmp/LA_HUC8_stream_labels.csv
cat /tmp/LA_HUC8_stream_labels.csv | sort > /tmp/LA_HUC8_stream_labels-sorted.csv
head -n 1 LP_03180004.csv | cat - /tmp/LA_HUC8_stream_labels-sorted.csv > LA_HUC8_stream_labels.csv
rm /tmp/LA_HUC8_stream_labels.csv /tmp/LA_HUC8_stream_labels-sorted.csv
```

### Load CSV into your GIS and join to NHD Flowline layer

## Example data

Example output that has been joined to NHD Flowlines for HUC8s in the state of Louisiana can be found [here](https://services9.arcgis.com/SfvtKAxCn62UWpRg/arcgis/rest/services/LWI_LabeledNHDStreams_2020_09_22/FeatureServer).
