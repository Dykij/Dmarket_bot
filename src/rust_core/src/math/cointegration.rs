/// Statistical Math Module for Pairs Trading
/// No unwrap() allowed. Returns Option/Result for safety.

pub struct CointegrationParams {
    pub mean: f64,
    pub std_dev: f64,
}

/// Calculates Z-Score for a given spread value
/// Formula: (Value - Mean) / StdDev
pub fn calculate_z_score(value: f64, params: &CointegrationParams) -> Option<f64> {
    // Lucas QA: Prevent division by zero if volatility is flat
    if params.std_dev <= 0.0 || params.std_dev.is_nan() {
        return None;
    }
    Some((value - params.mean) / params.std_dev)
}

/// Pearson Correlation Coefficient
/// Requires two equal-length slices.
pub fn calculate_correlation(x: &[f64], y: &[f64]) -> Option<f64> {
    if x.len() != y.len() || x.len() < 2 {
        return None;
    }

    let n = x.len() as f64;
    
    let mut sum_x = 0.0;
    let mut sum_y = 0.0;
    let mut sum_xy = 0.0;
    let mut sum_x2 = 0.0;
    let mut sum_y2 = 0.0;

    for i in 0..x.len() {
        sum_x += x[i];
        sum_y += y[i];
        sum_xy += x[i] * y[i];
        sum_x2 += x[i] * x[i];
        sum_y2 += y[i] * y[i];
    }

    let numerator = n * sum_xy - sum_x * sum_y;
    let denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)).sqrt();

    if denominator == 0.0 {
        return None;
    }

    Some(numerator / denominator)
}
