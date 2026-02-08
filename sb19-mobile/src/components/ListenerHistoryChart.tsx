import React, { useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Dimensions } from 'react-native';
import { LineChart } from 'react-native-gifted-charts';
import { HistoryPoint, DateRange } from '../types/data';
import { colors } from '../theme/colors';
import { formatNumber, formatDateShort } from '../utils/formatters';
import { filterHistoryByRange } from '../utils/calculations';
import { getArtistColor } from '../theme/colors';

const RANGES: { key: DateRange; label: string }[] = [
  { key: '7', label: '7D' },
  { key: '30', label: '30D' },
  { key: '90', label: '90D' },
  { key: 'all', label: 'All' },
];

interface SingleChartProps {
  history: HistoryPoint[];
  range: DateRange;
  onRangeChange: (range: DateRange) => void;
}

interface MultiChartProps {
  datasets: { name: string; history: HistoryPoint[] }[];
  range: DateRange;
  onRangeChange: (range: DateRange) => void;
}

type ListenerHistoryChartProps = SingleChartProps | MultiChartProps;

function isMulti(props: ListenerHistoryChartProps): props is MultiChartProps {
  return 'datasets' in props;
}

export default function ListenerHistoryChart(props: ListenerHistoryChartProps) {
  const { range, onRangeChange } = props;
  const screenWidth = Dimensions.get('window').width - 48;

  const chartData = useMemo(() => {
    if (isMulti(props)) {
      return props.datasets.map((ds, i) => {
        const filtered = filterHistoryByRange(ds.history, range);
        return {
          name: ds.name,
          color: getArtistColor(ds.name, i),
          data: filtered.map(p => ({
            value: p.listeners,
            label: '',
            dataPointText: '',
          })),
        };
      });
    } else {
      const filtered = filterHistoryByRange(props.history, range);
      return [{
        name: 'listeners',
        color: colors.primary,
        data: filtered.map(p => ({
          value: p.listeners,
          label: '',
          dataPointText: '',
        })),
      }];
    }
  }, [props, range]);

  // Compute step & labels
  const primaryData = chartData[0]?.data || [];
  const totalPoints = primaryData.length;
  const maxLabels = 5;
  const labelStep = Math.max(1, Math.floor(totalPoints / maxLabels));

  // Add labels to primary data
  if (!isMulti(props)) {
    const filtered = filterHistoryByRange(props.history, range);
    primaryData.forEach((d, i) => {
      if (i % labelStep === 0 || i === totalPoints - 1) {
        d.label = formatDateShort(filtered[i]?.date || '');
      }
    });
  }

  if (primaryData.length < 2) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Listener History</Text>
        <View style={styles.emptyChart}>
          <Text style={styles.emptyText}>Not enough data for chart</Text>
        </View>
      </View>
    );
  }

  // Compute y-axis range
  const allValues = chartData.flatMap(ds => ds.data.map(d => d.value));
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const padding = (maxVal - minVal) * 0.1 || maxVal * 0.1;
  const yMin = Math.max(0, Math.floor(minVal - padding));

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Listener History</Text>
        <View style={styles.rangeRow}>
          {RANGES.map(r => (
            <TouchableOpacity
              key={r.key}
              style={[styles.rangeBtn, range === r.key && styles.rangeBtnActive]}
              onPress={() => onRangeChange(r.key)}
            >
              <Text style={[styles.rangeBtnText, range === r.key && styles.rangeBtnTextActive]}>
                {r.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Legend for multi-line */}
      {isMulti(props) && (
        <View style={styles.legend}>
          {chartData.map(ds => (
            <View key={ds.name} style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: ds.color }]} />
              <Text style={styles.legendText}>{ds.name}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={styles.chartWrapper}>
        <LineChart
          data={chartData[0].data}
          data2={chartData[1]?.data}
          data3={chartData[2]?.data}
          data4={chartData[3]?.data}
          color={chartData[0].color}
          color2={chartData[1]?.color}
          color3={chartData[2]?.color}
          color4={chartData[3]?.color}
          width={screenWidth}
          height={220}
          spacing={Math.max(2, screenWidth / Math.max(primaryData.length - 1, 1))}
          initialSpacing={0}
          endSpacing={0}
          thickness={3}
          hideDataPoints={totalPoints >= 30}
          dataPointsRadius={3}
          dataPointsColor={chartData[0].color}
          curved
          yAxisColor="transparent"
          xAxisColor={colors.border}
          yAxisTextStyle={{ color: colors.textMuted, fontSize: 11 }}
          xAxisLabelTextStyle={{ color: colors.textMuted, fontSize: 10 }}
          noOfSections={4}
          yAxisOffset={yMin}
          formatYLabel={(val: string) => formatNumber(Number(val))}
          backgroundColor="transparent"
          rulesColor={colors.border}
          rulesType="dashed"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 8,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: '700',
  },
  rangeRow: {
    flexDirection: 'row',
    gap: 4,
  },
  rangeBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: colors.surface,
  },
  rangeBtnActive: {
    backgroundColor: colors.primary,
  },
  rangeBtnText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '600',
  },
  rangeBtnTextActive: {
    color: '#fff',
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 12,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendText: {
    color: colors.textSecondary,
    fontSize: 13,
  },
  chartWrapper: {
    marginLeft: -10,
  },
  emptyChart: {
    height: 180,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 12,
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 14,
  },
});
