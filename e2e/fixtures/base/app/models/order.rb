class Order < ApplicationRecord
  has_many :line_items

  def total_cents
    line_items.sum(:amount_cents)
  end
end
