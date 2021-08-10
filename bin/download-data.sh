#!/bin/bash

mkdir -p /tmp/data
cd /tmp/data

# Download data
echo "Downloading NHDPlus V2 data..."
wget https://s3.amazonaws.com/edap-nhdplus/NHDPlusV21/Data/NationalData/NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z
# Uncompress
echo "Uncompressing NHDPlus V2 data..."
7z x NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z

# Export to SpatiaLite/SQLite for easy querying from Python
echo "Building NHDFlowline_Network SpatiaLite database..."
ogr2ogr -progress -f "SQLite" -dsco "SPATIALITE=YES" NHDFlowline_Network.spatialite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb NHDFlowline_Network
echo "Building NHD_PlusFlow SQLite database..."
ogr2ogr -progress -f "SQLite" NHD_PlusFlow.sqlite NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb PlusFlow

# Add indexes for faster searching
echo "Indexing NHDFlowline_Network.spatialite..."
sqlite3 NHDFlowline_Network.spatialite \
"create index if not exists nhd_flow_reachcode_idx on nhdflowline_network (reachcode COLLATE NOCASE); \
create index if not exists nhd_flow_comid_idx on nhdflowline_network (comid);"

echo "Indexing NHD_PlusFlow.sqlite..."
sqlite3 NHD_PlusFlow.sqlite \
"create index if not exists nhd_plusflow_tocomid_idx on plusflow (tocomid); \
create index if not exists nhd_plusflow_fromcomid_idx on plusflow (fromcomid);"

# Clean-up downloaded files
echo "Cleaning up download file..."
rm -f NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z

cd -

echo "Done."
