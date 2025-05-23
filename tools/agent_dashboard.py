#!/usr/bin/env python3
# Filename: agent_dashboard.py
import argparse
import mysql.connector
import configparser
import time
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table

ACCESS_FILE = "../private/.mariadb_access"

console = Console()

def connect_db():
    config = configparser.ConfigParser()
    config.read(ACCESS_FILE)
    creds = config['client']
    return mysql.connector.connect(
        host=creds['host'],
        port=int(creds.get('port', 3306)),
        user=creds['user'],
        password=creds['password'],
        database=creds['database']
    )

def show_agent_status():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT locked_by_agent AS agent, performance_rating,
               MAX(updated_at) AS last_seen
        FROM conversations
        WHERE locked_by_agent IS NOT NULL
        GROUP BY locked_by_agent, performance_rating
    """)

    rows = cursor.fetchall()
    table = Table(title="Agentenstatus")
    table.add_column("Agent")
    table.add_column("Letzte Aktivität")
    table.add_column("Leistung")

    for row in rows:
        agent, last_seen, perf = row[0], row[2], row[1]
        table.add_row(
            agent,
            last_seen.strftime('%Y-%m-%d %H:%M:%S') if last_seen else '-',
            f"{perf:.2f}" if perf is not None else "-"
        )

    console.print(table)
    cursor.close()
    conn.close()

def show_agent_performance():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.agent AS agent_name,
               COUNT(c.id) AS processed,
               SUM(c.token_count) AS total_tokens,
               AVG(TIMESTAMPDIFF(SECOND, c.processing_started_at, c.processing_finished_at)) AS avg_duration
        FROM conversations c
        JOIN agent_log a ON c.locked_by_agent = a.agent
        WHERE c.processing_started_at IS NOT NULL AND c.processing_finished_at IS NOT NULL
        GROUP BY a.agent
        ORDER BY processed DESC
    """)
    rows = cursor.fetchall()

    table = Table(title="Agenten-Performance", show_lines=True)
    table.add_column("Agent")
    table.add_column("Verarbeitet")
    table.add_column("Tokens gesamt")
    table.add_column("Ø Dauer (Sekunden)")

    for row in rows:
        table.add_row(
            row['agent_name'],
            str(row['processed']),
            str(row['total_tokens'] or 0),
            f"{row['avg_duration']:.2f}" if row['avg_duration'] else "-"
        )

    console.print(table)
    cursor.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Agent Monitoring Dashboard")
    parser.add_argument(
        "--mode",
        choices=["status", "perf"],
        default="status",
        help="Anzeigemodus: 'status' (Agentenzustand) oder 'perf' (Leistungskennzahlen)"
    )
    args = parser.parse_args()

    if args.mode == "status":
        show_agent_status()
    elif args.mode == "perf":
        show_agent_performance()

if __name__ == "__main__":
    main()
