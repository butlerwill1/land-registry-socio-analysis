import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCompactCurrency } from "../lib/metrics";
import type { TransactionYear } from "../types";

export function PriceTrend({ history, year }: { history: TransactionYear[]; year: number }) {
  const data = useMemo(
    () => history.filter((point) => point.year <= year && point.medianPrice !== null).slice(-15),
    [history, year],
  );

  return (
    <div className="trend-chart" aria-label="Median flat price trend chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="#e5e9e7" strokeDasharray="3 3" />
          <XAxis dataKey="year" tickLine={false} axisLine={false} minTickGap={26} />
          <YAxis
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => formatCompactCurrency(Number(value))}
          />
          <Tooltip
            formatter={(value) => [formatCompactCurrency(Number(value)), "Median price"]}
            labelFormatter={(label) => String(label)}
            contentStyle={{ borderRadius: 4, borderColor: "#cfd8d4", boxShadow: "0 8px 24px rgba(18, 40, 35, .12)" }}
          />
          <Line
            dataKey="medianPrice"
            type="monotone"
            stroke="#087a6b"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#087a6b", stroke: "#ffffff", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
