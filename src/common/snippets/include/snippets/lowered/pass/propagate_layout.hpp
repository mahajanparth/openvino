// Copyright (C) 2023 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//

#pragma once

#include "pass.hpp"

namespace ov {
namespace snippets {
namespace lowered {
namespace pass {

/**
 * @interface PropagateLayout
 * @brief Propagate layout from Parameter child to parameter and from Result Parent to Result. This is needed to calculate
 * proper data pointer offsets in the Kernel;
 * @ingroup snippets
 */
class PropagateLayout : public RangedPass {
public:
    OPENVINO_RTTI("PropagateLayout", "RangedPass")
    bool run(lowered::LinearIR& linear_ir, lowered::LinearIR::constExprIt begin, lowered::LinearIR::constExprIt end) override;
};

} // namespace pass
} // namespace lowered
} // namespace snippets
} // namespace ov
