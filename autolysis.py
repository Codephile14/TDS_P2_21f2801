import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import base64
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from PIL import Image
import sys

# Constants
PROXY_URL = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
README_FILENAME = "README.md"

def analyze_csv(file_path):
    """Load and perform basic analysis on a CSV file."""
    try:
        # Try reading the CSV with default encoding
        data = pd.read_csv(file_path)
    except UnicodeDecodeError:
        # If UTF-8 fails, fall back to ISO-8859-1
        data = pd.read_csv(file_path, encoding='ISO-8859-1')

    summary = data.describe(include="all").transpose()
    missing = data.isnull().sum()

    numerical_data = data.select_dtypes(include=[np.number])
    if not numerical_data.empty:
        correlation_matrix = numerical_data.corr()
    else:
        correlation_matrix = None

    basic_results = {
        "num_rows": len(data),
        "num_columns": len(data.columns),
        "missing_values": missing.to_dict(),
        "summary_statistics": summary.to_dict(),
        "correlation_matrix": correlation_matrix.to_dict() if correlation_matrix is not None else None
    }
    return data, basic_results


def perform_advanced_analysis(data):
    """Perform advanced data analysis."""
    results = {}
    data_numeric = data.select_dtypes(include=[np.number]).dropna()

    # Outlier detection
    isolation_forest = IsolationForest(random_state=42)
    if not data_numeric.empty:
        outliers = isolation_forest.fit_predict(data_numeric)
        results["outliers"] = (outliers == -1).sum()

    # Clustering
    if len(data_numeric.columns) > 1:
        data_numeric_filled = data_numeric.fillna(data_numeric.mean())
        kmeans = KMeans(n_clusters=3, random_state=42, n_init="auto")
        clusters = kmeans.fit_predict(data_numeric_filled)
        results["clusters"] = kmeans.cluster_centers_.tolist()
        data["cluster"] = np.nan
        data.loc[data_numeric.index, "cluster"] = clusters

    # Regression analysis
    if len(data_numeric.columns) > 1:
        x, y = data_numeric.iloc[:, :-1], data_numeric.iloc[:, -1]
        regression = LinearRegression().fit(x, y)
        results["regression_coefficients"] = regression.coef_.tolist()

    return results

def send_to_llm(context, findings):
    """Send data summary and findings to the AI Proxy for insights and conclusion."""
    headers = {
        "Authorization": f"Bearer {os.environ.get('AIPROXY_TOKEN')}",
        "Content-Type": "application/json",
    }

    prompt = f"""
You are analyzing a dataset provided for analysis.

### Data Overview ###
The dataset contains {context['num_rows']} rows and {context['num_columns']} columns. Here are the column names: {list(context['missing_values'].keys())}.

### Analysis Conducted ###
Basic analysis includes:
- Summary Statistics: {context['summary_statistics']}.
- Missing Values: {context['missing_values']}.

Advanced analysis includes:
- Outlier detection: {findings.get('outliers', 'No outliers found')} potential outliers detected.
- Clustering: {findings.get('clusters', 'Clustering not applicable')}.
- Regression Coefficients: {findings.get('regression_coefficients', 'Regression analysis not performed')}.

### Instructions ###
Write a story about:
1. The data received.
2. The analysis carried out.
3. The insights discovered.
4. Implications of the findings and suggested next steps.
"""

    def make_request(prompt):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an AI data analyst."},
                {"role": "user", "content": prompt}
            ],
        }
        response = requests.post(PROXY_URL, headers=headers, json=payload)
        response.raise_for_status()  # Raise error if the request fails
        return response.json()["choices"][0]["message"]["content"]

    # Generate response
    story = make_request(prompt)
    return story


def create_visualizations(data):
    visualizations = []

    numerical_data = data.select_dtypes(include=[np.number])
    if not numerical_data.empty:
        # Correlation Heatmap
        plt.figure(figsize=(10, 8))
        sns.heatmap(numerical_data.corr(), annot=True, cmap="coolwarm")
        plt.title("Correlation Heatmap")
        heatmap_path = "correlation_heatmap.png"
        plt.savefig(heatmap_path)
        plt.close()
        visualizations.append(heatmap_path)

        # Outlier Detection Boxplot
        plt.figure(figsize=(12, 6))
        sns.boxplot(data=numerical_data)
        plt.title("Boxplot Analysis for Outliers")
        plt.xlabel("Features")
        plt.ylabel("Values")
        boxplot_path = "outlier_boxplot.png"
        plt.savefig(boxplot_path)
        plt.close()
        visualizations.append(boxplot_path)

        # Cluster Analysis Plot
        if len(numerical_data.columns) > 1:
            data_numeric_filled = numerical_data.fillna(numerical_data.mean())
            kmeans = KMeans(n_clusters=3, random_state=42, n_init="auto")
            clusters = kmeans.fit_predict(data_numeric_filled)
            plt.figure(figsize=(10, 6))
            plt.scatter(numerical_data.iloc[:, 0], numerical_data.iloc[:, 1], c=clusters, cmap="viridis", label="Clusters")
            plt.title("Cluster Analysis")
            plt.xlabel("First Numeric Feature")
            plt.ylabel("Second Numeric Feature")
            cluster_path = "cluster_analysis.png"
            plt.savefig(cluster_path)
            plt.close()
            visualizations.append(cluster_path)

    return visualizations

def generate_readme(story, visualizations):
    with open(README_FILENAME, "w") as f:
        f.write("# Dataset Analysis Report\n\n")
        f.write("## 1. Analysis Story\n")
        f.write(f"{story}\n\n")
        f.write("## 2. Visualizations\n")
        for vis in visualizations:
            f.write(f"![{os.path.splitext(vis)[0]}]({vis})\n")

def main(file_path):
    try:
        # Step 1: Analyze CSV
        data, basic_results = analyze_csv(file_path)
        
        # Step 2: Perform Advanced Analysis
        advanced_results = perform_advanced_analysis(data)
        
        # Step 3: Send Summary to LLM
        story = send_to_llm(basic_results, advanced_results)
        
        # Step 4: Create Visualizations
        visualizations = create_visualizations(data)
        
        # Step 5: Generate README Report
        generate_readme(story, visualizations)
        
        print(f"Analysis completed successfully. Results saved in {README_FILENAME}.")
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

# Run the script if executed directly
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <path_to_csv_file>", file=sys.stderr)
        sys.exit(1)
    csv_file_path = sys.argv[1]
    main(csv_file_path)

