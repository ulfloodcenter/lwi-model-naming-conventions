#!/bin/bash

mkdir -p /tmp/data
cd /tmp/data

# Download data
wget https://s3.amazonaws.com/edap-nhdplus/NHDPlusV21/Data/NationalData/NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z
# Uncompress
7z x NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z

# Export to SQLite
ogr2ogr -f "SQLite" -dsco "SPATIALITE=YES" NHDFlowline_Network.spatialite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb NHDFlowline_Network
ogr2ogr -f "SQLite" NHD_PlusFlow.sqlite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb PlusFlow

# Add indexes for faster searching
sqlite3 NHDFlowline_Network.spatialite \
"create index if not exists nhd_flow_reachcode_idx on nhdflowline_network (reachcode COLLATE NOCASE); \
create index if not exists nhd_flow_comid_idx on nhdflowline_network (comid);"

sqlite3NHD_PlusFlow.sqlite \
"create index if not exists nhd_plusflow_tocomid_idx on plusflow (tocomid); \
create index if not exists nhd_plusflow_fromcomid_idx on plusflow (fromcomid);"

# Clean-up downloaded files
rm NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z

cd -
