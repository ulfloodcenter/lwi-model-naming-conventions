# LWI Model Naming Conventions: Stream naming algorithm

## License
Louisiana Watershed Initiative (LWI) Stream Naming Convention Algorithm.
Copyright (C) 2021-present State of Louisiana, Division of Administration, Office of Community Development.

This program was developed by researchers at the [Louisiana Watershed Flood Center](https://floodcenter.louisiana.edu)
of the University of Louisiana at Lafayette with funding from the State of Louisiana, Division of Administration,
Office of Community Development under the LWI program. The LWI is funded by Community Development Block Grant
Mitigation funds from U.S. Department of Housing and Urban Development.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with this program.
If not, see <https://www.gnu.org/licenses/>.

## Setup

### Pre-requisites
- Unix-like environment ([WSL](https://docs.microsoft.com/en-us/windows/wsl/about) should work)
- Python 3.7+
- GDAL 3+ (version 2+ may work as well)
- SQLite 3
- 7z
- wget

### Download and prepare data
```
./bin/download-data.sh
```

> This will take a while. Go get coffee, or lunch.

### Installation
```
git clone <PUT_URL_HERE>
cd <PUT_CLONED_DIR_HERE>
python3 -m venv venv
source venv/bin/activate
python3 setup.py install
```

## Usage

### Label streams (using NHDPlus V2 data)
```
mkdir -p output
lwi-label-nhd-streams -f data/NHDFlowline_Network.spatialite -p data/NHD_PlusFlow.sqlite
```
> Note: To encode stream level labels as [base32](https://www.crockford.com/base32.html) instead of hexadecimal,
> add the `--base32` command line option.

By default, this will use the file `input/LWI_watersheds.csv` to control which HUC8 watersheds will have
their streams labeled, and also control what the two-letter watershed codes are to be used for each HUC8.
To use another watershed definition file, use the `-w` option. Use the `--help` to see all options.

Output will be stored in a directory named `output`.

### Combine output into one CSV file and add header
```
tail -q -n +2 *.csv > /tmp/LA_HUC8_stream_labels.csv
cat /tmp/LA_HUC8_stream_labels.csv | sort > /tmp/LA_HUC8_stream_labels-sorted.csv
head -n 1 AA_08080101.csv | cat - /tmp/LA_HUC8_stream_labels-sorted.csv > LA_HUC8_stream_labels.csv
rm /tmp/LA_HUC8_stream_labels.csv /tmp/LA_HUC8_stream_labels-sorted.csv
```

## Appendix: setting up and using with NHDPlus HR data
NHDPlus HD currently (August 2021) seems to lack flow topology information in the NHDPlusFlow table needed to
successfully run the LWI naming algorithm. However, the instructions below are included as a starting point for
future use of NHDPlus HR.

### Extract HUC4-based data for all of Louisiana
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
```
sqlite3 NHDPlusHR-LA.sqlite \
"create index if not exists nhdflowline_nhdplusid_idx on nhdflowline (nhdplusid); \
create index if not exists nhdplusflowlinevaa_nhdplusid_idx on nhdplusflowlinevaa (nhdplusid); \
create index if not exists nhdplusflow_fromnhdpid_idx on nhdplusflow(fromnhdpid); \
create index if not exists nhdplusflow_tonhdpid_idx on nhdplusflow(tonhdpid);"
```

### Usage
```
mkdir -p output
lwi-label-nhd-streams -f /path/to/NHDFlowline_Network.spatialite --nhdhr
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
head -n 1 AA_08080101.csv | cat - /tmp/LA_HUC8_stream_labels-sorted.csv > LA_HUC8_stream_labels.csv
rm /tmp/LA_HUC8_stream_labels.csv /tmp/LA_HUC8_stream_labels-sorted.csv
```

### Load CSV into your GIS and join to NHD Flowline layer

## Example data

Example output that has been joined to NHD Flowlines for HUC8s in the state of Louisiana can be found [here](https://services9.arcgis.com/SfvtKAxCn62UWpRg/arcgis/rest/services/LWI_LabeledNHDStreams_2020_09_22/FeatureServer).
