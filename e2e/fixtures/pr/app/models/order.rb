class Order < ApplicationRecord
  has_many :line_items

  def total_cents
    line_items.sum(:amount_cents)
  end

  # PLANTED: N+1 — no eager loading, and the two writes are not wrapped
  # in a transaction, so a failure halfway leaves the order inconsistent.
  def self.recalculate_all
    Order.all.each do |order|
      order.update!(total_cache_cents: order.line_items.sum(:amount_cents))
      order.audit_logs.create!(action: "recalculated")
    end
  end

  # PLANTED: money as a float, against the convention in README.md
  def total_display
    total_cents / 100.0
  end
end
