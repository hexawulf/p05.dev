/* Curated datasets and joint presets for p05.dev */

export const SAMPLE_DATASETS = [
  {
    id: "latency",
    label: "API Latency (ms, log-normal)",
    binRule: "fd",
    data: "18.4, 24.1, 15.2, 31.8, 12.6, 22.0, 44.5, 19.7, 27.3, 14.9, 52.1, 21.4, 16.8, 35.0, 28.6, 13.4, 64.2, 23.9, 17.5, 29.8, 41.0, 20.1, 15.8, 33.4, 25.5, 89.0, 19.2, 26.7",
  },
  {
    id: "heights",
    label: "Measurements (Normal + outlier)",
    binRule: "fd",
    data: "171.2, 168.4, 174.9, 169.1, 173.5, 176.0, 166.8, 172.3, 170.5, 175.4, 167.2, 171.8, 173.1, 169.9, 174.2, 170.1, 165.4, 172.8, 177.1, 168.9, 171.5, 173.7, 169.4, 194.5",
  },
  {
    id: "wait_times",
    label: "Inter-arrival Times (Exponential)",
    binRule: "scott",
    data: "0.4, 1.8, 0.2, 3.1, 0.9, 0.5, 2.4, 1.1, 4.7, 0.3, 1.5, 0.7, 2.9, 0.1, 5.4, 1.2, 0.6, 2.0, 0.8, 3.6, 1.4, 0.2, 1.9, 0.5",
  },
];

export const JOINT_PRESETS = [
  {
    id: "dep-2x2",
    label: "Dependent 2×2",
    xValues: [0, 1],
    yValues: [0, 1],
    matrix: [
      [0.1, 0.2],
      [0.3, 0.4],
    ],
  },
  {
    id: "indep-2x2",
    label: "Independent 2×2",
    xValues: [0, 1],
    yValues: [0, 1],
    matrix: [
      [0.12, 0.18],
      [0.28, 0.42],
    ],
  },
  {
    id: "corr-3x2",
    label: "Correlated 3×2",
    xValues: [0, 1, 2],
    yValues: [0, 1],
    matrix: [
      [0.25, 0.05],
      [0.15, 0.2],
      [0.05, 0.3],
    ],
  },
];
