from decimal import Decimal

from django.db import OperationalError, ProgrammingError
from django.db.models import Sum

from analytics.models import MarketShareSnapshot
from dispatches.models import Dispatch
from monitoring.models import Alert
from omcs.models import OMC
from receipts.models import ProductReceipt
from revenue.models import RevenueEntry
from sales.models import OMCSalesEntry
from tanks.models import Tank, TankStockEntry


def decimal_value(value):
    return Decimal(value or 0)


def dashboard_snapshot():
    try:
        latest_market_date = MarketShareSnapshot.objects.order_by("-snapshot_date").values_list(
            "snapshot_date", flat=True
        ).first()
        latest_market = MarketShareSnapshot.objects.filter(snapshot_date=latest_market_date) if latest_market_date else MarketShareSnapshot.objects.none()
        latest_entries = TankStockEntry.objects.select_related("tank", "tank__terminal", "tank__product").order_by(
            "-entry_date", "-created_at"
        )
        latest_receipts = ProductReceipt.objects.select_related("terminal", "product", "supplier").order_by(
            "-receipt_date", "-created_at"
        )
        latest_dispatches = Dispatch.objects.select_related("terminal", "product", "omc").order_by(
            "-dispatch_date", "-created_at"
        )
        latest_sales = OMCSalesEntry.objects.select_related("terminal", "product", "omc").order_by(
            "-sale_date", "-created_at"
        )
        latest_revenue = RevenueEntry.objects.select_related("terminal", "product", "omc").order_by(
            "-revenue_date", "-created_at"
        )
        alerts = Alert.objects.select_related("terminal", "tank", "product", "omc").order_by("-triggered_at")

        current_stock = decimal_value(Tank.objects.aggregate(total=Sum("current_stock_liters"))["total"])
        total_receipts = decimal_value(ProductReceipt.objects.aggregate(total=Sum("quantity_received"))["total"])
        total_dispatches = decimal_value(Dispatch.objects.aggregate(total=Sum("quantity_dispatched"))["total"])
        omc_sales_volume = decimal_value(OMCSalesEntry.objects.aggregate(total=Sum("volume_liters"))["total"])
        revenue_total = decimal_value(RevenueEntry.objects.aggregate(total=Sum("amount"))["total"])

        stock_trends = [
            {
                "label": entry.entry_date.strftime("%d %b"),
                "value": float(entry.closing_stock),
                "terminal": entry.tank.terminal.name,
            }
            for entry in latest_entries[:7]
        ][::-1]
        receipts_vs_dispatches = [
            {
                "label": receipt.receipt_date.strftime("%d %b"),
                "receipts": float(receipt.quantity_received),
                "dispatches": float(
                    Dispatch.objects.filter(dispatch_date=receipt.receipt_date).aggregate(total=Sum("quantity_dispatched"))["total"]
                    or 0
                ),
            }
            for receipt in latest_receipts[:6]
        ][::-1]
        market_share = [
            {
                "label": snapshot.omc.name,
                "share": float(snapshot.market_share_percent),
            }
            for snapshot in latest_market.select_related("omc").order_by("-market_share_percent")[:5]
        ]
        revenue_vs_volume = [
            {
                "label": row.revenue_date.strftime("%b %Y"),
                "revenue": float(row.amount),
                "volume": float(row.volume_liters),
            }
            for row in latest_revenue[:6]
        ][::-1]
        product_flow = [
            {
                "label": row["product__name"],
                "receipts": float(row["receipts_total"] or 0),
                "dispatches": float(row["dispatches_total"] or 0),
            }
            for row in ProductReceipt.objects.values("product__name")
            .annotate(receipts_total=Sum("quantity_received"), dispatches_total=Sum("product__dispatches__quantity_dispatched"))
            .order_by("-receipts_total", "product__name")[:5]
        ]
        alert_breakdown = [
            {
                "label": label,
                "count": alerts.filter(severity=severity).count(),
                "severity": severity,
            }
            for severity, label in Alert.Severity.choices
        ]

        terminal_summary = Tank.objects.select_related("terminal", "product").order_by("terminal__name", "name")[:8]
        omc_ranking = (
            OMC.objects.annotate(total_volume=Sum("sales_entries__volume_liters"))
            .order_by("-total_volume", "name")[:6]
        )

        latest_activity = (
            [{"type": "Receipt", "date": item.receipt_date, "description": f"{item.product.name} receipt at {item.terminal.name}", "quantity": item.quantity_received}
             for item in latest_receipts[:4]]
            + [{"type": "Dispatch", "date": item.dispatch_date, "description": f"{item.product.name} dispatch to {item.omc.name}", "quantity": item.quantity_dispatched}
               for item in latest_dispatches[:4]]
            + [{"type": "Sales", "date": item.sale_date, "description": f"{item.omc.name} sales submission", "quantity": item.volume_liters}
               for item in latest_sales[:4]]
        )
        latest_activity = sorted(latest_activity, key=lambda row: row["date"], reverse=True)[:8]

        return {
            "database_ready": True,
            "kpis": {
                "current_stock": current_stock,
                "total_receipts": total_receipts,
                "total_dispatches": total_dispatches,
                "omc_sales_volume": omc_sales_volume,
                "revenue": revenue_total,
                "alerts": alerts.filter(status=Alert.Status.OPEN).count(),
            },
            "stock_trends": stock_trends,
            "receipts_vs_dispatches": receipts_vs_dispatches,
            "market_share": market_share,
            "revenue_vs_volume": revenue_vs_volume,
            "product_flow": product_flow,
            "alert_breakdown": alert_breakdown,
            "latest_activity": latest_activity,
            "terminal_summary": terminal_summary,
            "omc_ranking": omc_ranking,
            "alerts": alerts[:8],
        }
    except (OperationalError, ProgrammingError):
        return {
            "database_ready": False,
            "database_message": "The new ZALA Terminal tables are not available yet. Run migrations to load terminal stock, revenue, monitoring, and market-share data.",
            "kpis": {
                "current_stock": Decimal("0"),
                "total_receipts": Decimal("0"),
                "total_dispatches": Decimal("0"),
                "omc_sales_volume": Decimal("0"),
                "revenue": Decimal("0"),
                "alerts": 0,
            },
            "stock_trends": [],
            "receipts_vs_dispatches": [],
            "market_share": [],
            "revenue_vs_volume": [],
            "product_flow": [],
            "alert_breakdown": [],
            "latest_activity": [],
            "terminal_summary": [],
            "omc_ranking": [],
            "alerts": [],
        }
