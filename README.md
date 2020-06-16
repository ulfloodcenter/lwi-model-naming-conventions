
# Label streams
```
python stream_naming_convention_experiments_label.py
```

# Concatenate output into one file
```
tail -q -n +2 *.csv > /tmp/LA_HUC8_stream_labels.csv
head -n 1 AA_03180004.csv | cat - /tmp/LA_HUC8_stream_labels.csv > LA_HUC8_stream_labels.csv
rm /tmp/LA_HUC8_stream_labels.csv
```
